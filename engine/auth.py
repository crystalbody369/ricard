# -*- coding: utf-8 -*-
"""ログイン認証＋紹介コード＋利用期限＋即停止（宝くじアプリの auth.py を移植）。

- パスワードは pbkdf2(sha256) でハッシュ化して保存（平文は持たない）
- 登録は「紹介コード」を持つ人だけ可能（コード無しは登録不可）
- 各ユーザーに利用期限(expires_on)・有効フラグ(enabled)・管理者フラグ(is_admin)
- 期限切れ／無効化はログイン不可＝管理者がいつでも即停止できる
- すべて永続ディスクの SQLite（store.get_conn）で管理
"""

import hashlib
import secrets
import datetime

from . import store

_ITER = 200_000
_MAX_FAILS = 5      # 連続失敗の上限（これに達するとロック）
_LOCK_MIN = 10      # ロック時間（分）


def init_auth():
    with store.get_conn() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                username     TEXT PRIMARY KEY,
                pw_hash      TEXT NOT NULL,
                salt         TEXT NOT NULL,
                expires_on   TEXT,
                enabled      INTEGER DEFAULT 1,
                is_admin     INTEGER DEFAULT 0,
                note         TEXT DEFAULT '',
                failed_count INTEGER DEFAULT 0,
                locked_until TEXT,
                created_at   TEXT DEFAULT (datetime('now','localtime'))
            )""")
        conn.execute(
            """CREATE TABLE IF NOT EXISTS invite_codes (
                code        TEXT PRIMARY KEY,
                enabled     INTEGER DEFAULT 1,
                max_uses    INTEGER DEFAULT 0,   -- 0 = 無制限
                used_count  INTEGER DEFAULT 0,
                expires_on  TEXT,                -- コード自体の有効期限（NULL=無期限）
                grant_days  INTEGER,             -- 登録者に与える利用日数（NULL=無期限）
                note        TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now','localtime'))
            )""")
        # 課金用カラムの移行（無料お試しの使用回数・購入クレジット）
        cols = [r[1] for r in conn.execute("PRAGMA table_info(users)").fetchall()]
        if "free_used" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN free_used INTEGER DEFAULT 0")
        if "credits" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0")
        if "free_quota" not in cols:   # この利用者に与えられた無料回数（NULL=既定値）
            conn.execute("ALTER TABLE users ADD COLUMN free_quota INTEGER")
        if "email" not in cols:   # パスワード再設定用のメールアドレス
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
        ic_cols = [r[1] for r in conn.execute("PRAGMA table_info(invite_codes)").fetchall()]
        if "grant_free" not in ic_cols:   # このコードで登録した人に与える無料回数（NULL=既定）
            conn.execute("ALTER TABLE invite_codes ADD COLUMN grant_free INTEGER")
        # パスワード再設定トークン（メールのリンクで本人が自分で再設定する）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS password_resets (
                token_hash TEXT PRIMARY KEY,
                username   TEXT,
                expires    TEXT,
                used       INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            )""")
        # 使用済みメール台帳：一度登録したメールは退会・削除後も再登録不可にする（管理者は例外）
        conn.execute(
            """CREATE TABLE IF NOT EXISTS used_emails (
                email      TEXT PRIMARY KEY,
                first_used TEXT DEFAULT (datetime('now','localtime'))
            )""")
        # 既存ユーザー（管理者以外）のメールを台帳へ取り込む（台帳導入前の人も削除後に再登録できないように）
        conn.execute(
            "INSERT OR IGNORE INTO used_emails(email) "
            "SELECT lower(email) FROM users "
            "WHERE email IS NOT NULL AND email <> '' AND is_admin = 0")
        # 管理者メールは再登録ブロックの例外。万一すでに台帳へ入っていたら取り除く
        conn.execute(
            "DELETE FROM used_emails WHERE email IN "
            "(SELECT lower(email) FROM users WHERE is_admin = 1 AND email <> '')")


def _valid_email(email):
    email = (email or "").strip()
    return bool(email) and "@" in email and "." in email.split("@")[-1] and len(email) <= 200


_RESET_TTL_MIN = 60   # 再設定リンクの有効時間（分）


def _tok_hash(raw):
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


def set_email(username, email):
    email = (email or "").strip()
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET email=? WHERE username=?", (email, username))


def get_email(username):
    with store.get_conn() as conn:
        r = conn.execute("SELECT email FROM users WHERE username=?", (username,)).fetchone()
    return (r["email"] or "") if r else ""


def create_reset_token(email):
    """メールから本人を特定し、再設定トークンを発行。
    戻り値 (username, raw_token) ／ 該当なしは None（存在は伏せる＝呼び出し側で同じ応答）。"""
    email = (email or "").strip()
    if not email:
        return None
    with store.get_conn() as conn:
        r = conn.execute("SELECT username FROM users WHERE lower(email)=lower(?) AND enabled=1",
                         (email,)).fetchone()
        if not r:
            return None
        username = r["username"]
        raw = secrets.token_urlsafe(32)
        expires = (datetime.datetime.now() + datetime.timedelta(minutes=_RESET_TTL_MIN)).isoformat()
        conn.execute("INSERT INTO password_resets(token_hash, username, expires, used) VALUES(?,?,?,0)",
                     (_tok_hash(raw), username, expires))
    return (username, raw)


def consume_reset_token(raw, new_password):
    """トークンが有効なら新パスワードを設定し、ロックも解除。戻り値 username／無効は None。"""
    if not raw or not new_password or len(new_password) < 6:
        return None
    th = _tok_hash(raw)
    now = datetime.datetime.now().isoformat()
    with store.get_conn() as conn:
        r = conn.execute("SELECT username, expires, used FROM password_resets WHERE token_hash=?",
                         (th,)).fetchone()
        if not r or r["used"] or (r["expires"] and now > r["expires"]):
            return None
        username = r["username"]
        salt = secrets.token_hex(16)
        conn.execute("UPDATE users SET pw_hash=?, salt=?, failed_count=0, locked_until=NULL WHERE username=?",
                     (_hash(new_password, salt), salt, username))
        conn.execute("UPDATE password_resets SET used=1 WHERE token_hash=?", (th,))
    return username


def get_balance(username, default_free):
    """無料残り・購入クレジット・合計を返す。各利用者の free_quota（無ければ既定値）を使う。"""
    with store.get_conn() as conn:
        r = conn.execute("SELECT free_used, credits, is_admin, free_quota FROM users WHERE username=?",
                         (username,)).fetchone()
    if not r:
        return {"free_remaining": 0, "credits": 0, "total": 0, "unlimited": False}
    if r["is_admin"]:
        return {"free_remaining": 0, "credits": 0, "total": 0, "unlimited": True}
    fq = r["free_quota"] if r["free_quota"] is not None else int(default_free)
    free_rem = max(0, fq - (r["free_used"] or 0))
    credits = r["credits"] or 0
    return {"free_remaining": free_rem, "credits": credits,
            "total": free_rem + credits, "unlimited": False}


def consume_consult(username, default_free):
    """相談を1回消費（無料枠を先に、無ければクレジット）。成功時 True＋残数。"""
    with store.get_conn() as conn:
        r = conn.execute("SELECT free_used, credits, is_admin, free_quota FROM users WHERE username=?",
                         (username,)).fetchone()
        if not r:
            return {"ok": False}
        if r["is_admin"]:
            return {"ok": True, "unlimited": True}
        free_used = r["free_used"] or 0
        credits = r["credits"] or 0
        fq = r["free_quota"] if r["free_quota"] is not None else int(default_free)
        if free_used < fq:
            conn.execute("UPDATE users SET free_used=free_used+1 WHERE username=?", (username,))
            return {"ok": True, "free_remaining": fq - free_used - 1, "credits": credits}
        if credits > 0:
            conn.execute("UPDATE users SET credits=credits-1 WHERE username=?", (username,))
            return {"ok": True, "free_remaining": 0, "credits": credits - 1}
        return {"ok": False, "no_balance": True}


def add_credits(username, n):
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET credits=COALESCE(credits,0)+? WHERE username=?",
                     (int(n), username))


def _hash(password, salt_hex):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), _ITER).hex()


def count_users():
    with store.get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def add_user(username, password, days=None, is_admin=False, note=""):
    """管理者などを直接追加（既存なら上書き）。days=None で無期限。"""
    username = (username or "").strip()
    if not username or not password:
        raise ValueError("ユーザー名とパスワードは必須です")
    salt = secrets.token_hex(16)
    pwh = _hash(password, salt)
    expires_on = ((datetime.date.today() + datetime.timedelta(days=int(days))).isoformat()
                  if days is not None else None)
    with store.get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO users
               (username, pw_hash, salt, expires_on, enabled, is_admin, note)
               VALUES (?, ?, ?, ?, 1, ?, ?)""",
            (username, pwh, salt, expires_on, 1 if is_admin else 0, note))


# ── 紹介コード ──────────────────────────────────────
def create_code(code, max_uses=0, grant_days=None, grant_free=None, expires_on=None, note=""):
    code = (code or "").strip()
    if not code:
        raise ValueError("コードを入力してください")
    with store.get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO invite_codes
               (code, enabled, max_uses, used_count, expires_on, grant_days, grant_free, note)
               VALUES (?, 1, ?, COALESCE((SELECT used_count FROM invite_codes WHERE code=?),0), ?, ?, ?, ?)""",
            (code, int(max_uses), code, expires_on, grant_days, grant_free, note))


def _live_uses(conn, code):
    """そのコードで実際に登録している利用者の数（削除すれば即減る）。"""
    r = conn.execute("SELECT COUNT(*) AS n FROM users WHERE note=?", ("紹介:" + code,)).fetchone()
    return r["n"] if r else 0


def list_codes():
    with store.get_conn() as conn:
        rows = conn.execute("SELECT * FROM invite_codes ORDER BY created_at DESC").fetchall()
        out = []
        today = datetime.date.today().isoformat()
        for r in rows:
            used = _live_uses(conn, r["code"])     # 実数（削除と連動）
            expired = bool(r["expires_on"]) and today > r["expires_on"]
            full = r["max_uses"] and used >= r["max_uses"]
            out.append({
                "code": r["code"], "enabled": bool(r["enabled"]),
                "max_uses": r["max_uses"], "used_count": used,
                "expires_on": r["expires_on"] or "無期限",
                "grant_days": r["grant_days"], "grant_free": r["grant_free"], "note": r["note"] or "",
                "状態": ("停止中" if not r["enabled"] else "期限切れ" if expired
                        else "上限到達" if full else "有効"),
            })
    return out


def set_code_enabled(code, enabled):
    with store.get_conn() as conn:
        conn.execute("UPDATE invite_codes SET enabled=? WHERE code=?",
                     (1 if enabled else 0, code))


def delete_code(code):
    with store.get_conn() as conn:
        conn.execute("DELETE FROM invite_codes WHERE code=?", (code,))


def _valid_code(conn, code):
    r = conn.execute("SELECT * FROM invite_codes WHERE code=?", (code,)).fetchone()
    if not r or not r["enabled"]:
        return None
    today = datetime.date.today().isoformat()
    if r["expires_on"] and today > r["expires_on"]:
        return None
    if r["max_uses"] and _live_uses(conn, code) >= r["max_uses"]:
        return None
    return r


def register_with_code(code, username, password, email=""):
    """紹介コードを使った新規登録。成功で expires_on を返す。メールは再設定用に必須。"""
    code = (code or "").strip()
    username = (username or "").strip()
    email = (email or "").strip()
    if not code:
        raise ValueError("紹介コードを入力してください")
    if not username or not password:
        raise ValueError("ユーザー名とパスワードを入力してください")
    if not _valid_email(email):
        raise ValueError("メールアドレスを正しく入力してください（パスワードを忘れた時の再設定に使います）")
    if len(password) < 6:
        raise ValueError("パスワードは6文字以上にしてください")
    with store.get_conn() as conn:
        cr = _valid_code(conn, code)
        if not cr:
            raise ValueError("紹介コードが無効です（存在しない・停止・期限切れ・上限到達）")
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("そのユーザー名は既に使われています。別の名前にしてください。")
        # メールは1つにつき1アカウント。さらに「使用済み台帳」で、退会・削除した後でも
        # 一度使ったメールは二度と再登録できない（大文字小文字は区別しない・管理者は例外）。
        email_lc = email.lower()
        if (conn.execute("SELECT 1 FROM users WHERE lower(email)=?", (email_lc,)).fetchone()
                or conn.execute("SELECT 1 FROM used_emails WHERE email=?", (email_lc,)).fetchone()):
            raise ValueError("このメールアドレスは既に使用されています。一度登録したメールアドレスは再登録できません。")
        salt = secrets.token_hex(16)
        pwh = _hash(password, salt)
        gd = cr["grant_days"]
        expires_on = ((datetime.date.today() + datetime.timedelta(days=int(gd))).isoformat()
                      if gd is not None else None)
        gf = cr["grant_free"]   # このコードが与える無料回数（NULL=既定）
        conn.execute(
            """INSERT INTO users (username, pw_hash, salt, expires_on, enabled, is_admin, note, free_quota, email)
               VALUES (?, ?, ?, ?, 1, 0, ?, ?, ?)""",
            (username, pwh, salt, expires_on, "紹介:" + code, gf, email))
        conn.execute("UPDATE invite_codes SET used_count=used_count+1 WHERE code=?", (code,))
        # 使用済みメール台帳に永久記録（このメールは今後アカウントを消しても再登録不可）。
        # register_with_code で作られる利用者は常に一般ユーザー（管理者ではない）なので必ず記録する。
        conn.execute("INSERT OR IGNORE INTO used_emails(email) VALUES(?)", (email_lc,))
    return expires_on


# ── ログイン ────────────────────────────────────────
def verify(username, password):
    username = (username or "").strip()
    with store.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row:
        return {"ok": False, "reason": "ユーザー名またはパスワードが違います。"}
    now = datetime.datetime.now()
    lu = row["locked_until"]
    if lu:
        try:
            lu_dt = datetime.datetime.fromisoformat(lu)
            if now < lu_dt:
                mins = int((lu_dt - now).total_seconds() // 60) + 1
                return {"ok": False, "reason": f"ロック中です。あと約{mins}分お待ちください。"}
        except (ValueError, TypeError):
            pass
    if _hash(password, row["salt"]) != row["pw_hash"]:
        new_fail = (row["failed_count"] or 0) + 1
        with store.get_conn() as conn:
            if new_fail >= _MAX_FAILS:
                locked = (now + datetime.timedelta(minutes=_LOCK_MIN)).isoformat()
                conn.execute("UPDATE users SET failed_count=0, locked_until=? WHERE username=?",
                             (locked, username))
                return {"ok": False, "reason": f"{_MAX_FAILS}回まちがえました。{_LOCK_MIN}分ロックします。"}
            conn.execute("UPDATE users SET failed_count=? WHERE username=?", (new_fail, username))
        return {"ok": False,
                "reason": f"ユーザー名またはパスワードが違います。（あと{_MAX_FAILS - new_fail}回でロック）"}
    if not row["enabled"]:
        return {"ok": False, "reason": "このアカウントは停止されています。管理者にお問い合わせください。"}
    if row["expires_on"] and datetime.date.today().isoformat() > row["expires_on"]:
        return {"ok": False, "reason": f"利用期限が切れています（{row['expires_on']} まで）。"}
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET failed_count=0, locked_until=NULL WHERE username=?", (username,))
    return {"ok": True, "is_admin": bool(row["is_admin"]), "expires_on": row["expires_on"]}


def check_active(username):
    """パスワード無しで「今使える状態か」を確認（クッキー復元時・即停止を効かせる）。"""
    username = (username or "").strip()
    with store.get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not row or not row["enabled"]:
        return {"ok": False}
    if row["expires_on"] and datetime.date.today().isoformat() > row["expires_on"]:
        return {"ok": False}
    return {"ok": True, "is_admin": bool(row["is_admin"]), "expires_on": row["expires_on"]}


# ── 管理 ────────────────────────────────────────────
def list_users():
    with store.get_conn() as conn:
        rows = conn.execute(
            "SELECT username, expires_on, enabled, is_admin, note, created_at, "
            "free_quota, free_used, credits, email "
            "FROM users ORDER BY is_admin DESC, username").fetchall()
    today = datetime.date.today().isoformat()
    out = []
    for r in rows:
        expired = bool(r["expires_on"]) and today > r["expires_on"]
        out.append({
            "username": r["username"], "登録日": (r["created_at"] or "")[:10],
            "expires_on": r["expires_on"] or "無期限",
            "enabled": bool(r["enabled"]), "is_admin": bool(r["is_admin"]),
            "note": r["note"] or "",
            "free_quota": r["free_quota"], "free_used": r["free_used"] or 0,
            "credits": r["credits"] or 0, "email": r["email"] or "",
            "状態": ("管理者" if r["is_admin"] else "停止中" if not r["enabled"]
                    else "期限切れ" if expired else "有効"),
        })
    return out


def set_enabled(username, enabled):
    with store.get_conn() as conn:
        if enabled:
            conn.execute("UPDATE users SET enabled=1, failed_count=0, locked_until=NULL WHERE username=?",
                         (username,))
        else:
            conn.execute("UPDATE users SET enabled=0 WHERE username=?", (username,))


def set_expiry(username, expires_on):
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET expires_on=? WHERE username=?", (expires_on, username))


def extend_days(username, days):
    new = (datetime.date.today() + datetime.timedelta(days=int(days))).isoformat()
    set_expiry(username, new)
    return new


def change_password(username, password):
    salt = secrets.token_hex(16)
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET pw_hash=?, salt=? WHERE username=?",
                     (_hash(password, salt), salt, username))


def reset_password(username):
    """管理者用：ランダムな仮パスワードを発行して設定し、その平文を返す（本人に伝える）。
    ロック中でも仮パスワードですぐ入れるよう、失敗回数とロックも同時に解除する。"""
    newpw = secrets.token_urlsafe(6)
    change_password(username, newpw)
    with store.get_conn() as conn:
        conn.execute("UPDATE users SET failed_count=0, locked_until=NULL WHERE username=?", (username,))
    return newpw


def delete_user(username):
    with store.get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username=?", (username,))
