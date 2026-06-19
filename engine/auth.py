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
def create_code(code, max_uses=0, grant_days=None, expires_on=None, note=""):
    code = (code or "").strip()
    if not code:
        raise ValueError("コードを入力してください")
    with store.get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO invite_codes
               (code, enabled, max_uses, used_count, expires_on, grant_days, note)
               VALUES (?, 1, ?, COALESCE((SELECT used_count FROM invite_codes WHERE code=?),0), ?, ?, ?)""",
            (code, int(max_uses), code, expires_on, grant_days, note))


def list_codes():
    with store.get_conn() as conn:
        rows = conn.execute("SELECT * FROM invite_codes ORDER BY created_at DESC").fetchall()
    out = []
    today = datetime.date.today().isoformat()
    for r in rows:
        expired = bool(r["expires_on"]) and today > r["expires_on"]
        full = r["max_uses"] and r["used_count"] >= r["max_uses"]
        out.append({
            "code": r["code"], "enabled": bool(r["enabled"]),
            "max_uses": r["max_uses"], "used_count": r["used_count"],
            "expires_on": r["expires_on"] or "無期限",
            "grant_days": r["grant_days"], "note": r["note"] or "",
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
    if r["max_uses"] and r["used_count"] >= r["max_uses"]:
        return None
    return r


def register_with_code(code, username, password):
    """紹介コードを使った新規登録。成功で expires_on を返す。"""
    code = (code or "").strip()
    username = (username or "").strip()
    if not code:
        raise ValueError("紹介コードを入力してください")
    if not username or not password:
        raise ValueError("ユーザー名とパスワードを入力してください")
    if len(password) < 6:
        raise ValueError("パスワードは6文字以上にしてください")
    with store.get_conn() as conn:
        cr = _valid_code(conn, code)
        if not cr:
            raise ValueError("紹介コードが無効です（存在しない・停止・期限切れ・上限到達）")
        if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
            raise ValueError("そのユーザー名は既に使われています。別の名前にしてください。")
        salt = secrets.token_hex(16)
        pwh = _hash(password, salt)
        gd = cr["grant_days"]
        expires_on = ((datetime.date.today() + datetime.timedelta(days=int(gd))).isoformat()
                      if gd is not None else None)
        conn.execute(
            """INSERT INTO users (username, pw_hash, salt, expires_on, enabled, is_admin, note)
               VALUES (?, ?, ?, ?, 1, 0, ?)""",
            (username, pwh, salt, expires_on, "紹介:" + code))
        conn.execute("UPDATE invite_codes SET used_count=used_count+1 WHERE code=?", (code,))
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
            "SELECT username, expires_on, enabled, is_admin, note, created_at "
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


def delete_user(username):
    with store.get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username=?", (username,))
