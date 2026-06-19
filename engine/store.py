# -*- coding: utf-8 -*-
"""固い保存役 — 永続ディスク上の SQLite に「当日の利用額」「IP/ユーザー別の回数」を記録。

再起動・再デプロイ・多重ワーカーでも消えない＝本物の固い上限の土台。
保存先は永続ディスク（Renderでは /var/data）。ローカルでは作業フォルダ内のファイル。
"""

import os
import sqlite3
import json
import datetime
import threading
from contextlib import contextmanager

_lock = threading.Lock()
_conn = None


@contextmanager
def get_conn():
    """認証・管理用の接続（row_factory付き・コミット＆クローズ）。auth.py から使う。"""
    path = _db_path()
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_settings():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")


def set_setting(key, value):
    _ensure_settings()
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings(key, value) VALUES(?, ?)",
                     (key, json.dumps(value)))


def get_setting(key, default=None):
    _ensure_settings()
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (ValueError, TypeError):
        return default


def _ensure_ri_docs():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS ri_docs ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, body TEXT, "
                     "created_at TEXT DEFAULT (datetime('now','localtime')))")
        # 旧テーブルからの移行：足りない列を追加（タグ・読みの強さ・判断型・大分類・注意点）
        have = set(r["name"] for r in conn.execute("PRAGMA table_info(ri_docs)").fetchall())
        for c in ("tags", "strength", "ptype", "cat", "note"):
            if c not in have:
                conn.execute("ALTER TABLE ri_docs ADD COLUMN %s TEXT DEFAULT ''" % c)


def add_ri_doc(title, body, tags="", strength="", ptype="", cat="", note=""):
    _ensure_ri_docs()
    title = (title or "").strip() or "（無題）"
    body = (body or "").strip()
    if not body:
        return
    with get_conn() as conn:
        conn.execute("INSERT INTO ri_docs(title, body, tags, strength, ptype, cat, note) "
                     "VALUES(?, ?, ?, ?, ?, ?, ?)",
                     (title, body, tags or "", strength or "", ptype or "", cat or "", note or ""))


def list_ri_docs():
    _ensure_ri_docs()
    with get_conn() as conn:
        rows = conn.execute("SELECT id, title, body, tags, strength, ptype, cat, note, created_at "
                            "FROM ri_docs ORDER BY id DESC").fetchall()
    return [{"id": r["id"], "title": r["title"] or "", "body": r["body"] or "",
             "tags": r["tags"] or "", "strength": r["strength"] or "",
             "ptype": r["ptype"] or "", "cat": r["cat"] or "", "note": r["note"] or "",
             "created_at": (r["created_at"] or "")[:10]} for r in rows]


def delete_ri_doc(doc_id):
    _ensure_ri_docs()
    with get_conn() as conn:
        conn.execute("DELETE FROM ri_docs WHERE id=?", (int(doc_id),))


def count_ri_docs():
    _ensure_ri_docs()
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM ri_docs").fetchone()["n"]


def _seed_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "ri_seed.json")


def _seed_entries():
    p = _seed_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, OSError):
        return []


def seed_version():
    """同梱データの版（ri_seed.version の文字列）。基本データを差し替えたら変わる。"""
    p = os.path.join(os.path.dirname(_seed_path()), "ri_seed.version")
    try:
        with open(p, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def imported_version():
    return get_setting("ri_seed_version", "") or ""


def seed_count():
    return len(_seed_entries())


def seed_is_current():
    """同梱の最新版が取り込み済みかどうか。"""
    sv = seed_version()
    return bool(sv) and (imported_version() == sv)


def seed_pending_count():
    """同梱データのうち、まだ知識ベースに入っていない件数。0なら取り込み済み。"""
    entries = _seed_entries()
    if not entries:
        return 0
    _ensure_ri_docs()
    with get_conn() as conn:
        existing = set(r["title"] for r in conn.execute("SELECT title FROM ri_docs").fetchall())
    return sum(1 for e in entries
               if (e.get("title") or "").strip() and (e.get("title") or "").strip() not in existing)


def _insert_seed_entries(conn, entries, existing):
    added = 0
    for e in entries:
        t = (e.get("title") or "").strip()
        b = (e.get("body") or "").strip()
        if not t or not b or t in existing:
            continue
        conn.execute("INSERT INTO ri_docs(title, body, tags, strength, ptype, cat, note) "
                     "VALUES(?, ?, ?, ?, ?, ?, ?)",
                     (t, b, e.get("tags") or "", e.get("strength") or "",
                      e.get("ptype") or "", e.get("cat") or "", e.get("note") or ""))
        existing.add(t)
        added += 1
    return added


def import_ri_seed():
    """同梱の ri_seed.json から、まだ無いタイトルの理を知識ベースへ追加取り込み。追加件数を返す。"""
    _ensure_ri_docs()
    entries = _seed_entries()
    if not entries:
        return 0
    with get_conn() as conn:
        existing = set(r["title"] for r in conn.execute("SELECT title FROM ri_docs").fetchall())
        added = _insert_seed_entries(conn, entries, existing)
    set_setting("ri_seed_version", seed_version())
    return added


def replace_ri_seed():
    """知識ベースを全消去し、同梱の最新版で入れ替える（基本データの差し替え）。件数を返す。
    ※管理者が手で足した理も一緒に消える。基本データを正式に更新するときに使う。"""
    _ensure_ri_docs()
    entries = _seed_entries()
    if not entries:
        return 0
    with get_conn() as conn:
        conn.execute("DELETE FROM ri_docs")
        added = _insert_seed_entries(conn, entries, set())
    set_setting("ri_seed_version", seed_version())
    return added


def _bigrams(s):
    s = (s or "").replace("\n", "").replace("\r", "").replace(" ", "").replace("　", "")
    if len(s) < 2:
        return set([s]) if s else set()
    return set(s[i:i + 2] for i in range(len(s) - 1))


def search_ri_docs(query, k=4, max_chars=2500):
    """相談文に関係する理だけを文字2-gramの重なりで探す（無料・ローカル・日本語/中国語可）。
    タイトル・タグ（＝現象/キーワード）に当たった分を重く見て、現象に効く理を優先する。
    上位k件・合計max_chars字まで。AIに渡るのはここで選ばれた分だけ＝コストは小さいまま。"""
    qg = _bigrams(query)
    if not qg:
        return []
    scored = []
    for d in list_ri_docs():
        key_g = _bigrams(d["title"] + " " + d.get("tags", ""))   # 現象・タグ＝検索の効きどころ
        body_g = _bigrams(d["body"])
        if not (key_g or body_g):
            continue
        # 現象・タグの一致は3倍重み、本文の一致は1倍
        score = 3 * len(qg & key_g) + len(qg & body_g)
        if score > 0:
            scored.append((score, d))
    scored.sort(key=lambda x: -x[0])
    out, total = [], 0
    for _, d in scored[:k]:
        body = d["body"]
        if total + len(body) > max_chars:
            body = body[:max(0, max_chars - total)]
        if not body:
            break
        out.append({"title": d["title"], "body": body, "strength": d.get("strength", "")})
        total += len(body)
        if total >= max_chars:
            break
    return out


def _ensure_profiles():
    with get_conn() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS profiles ("
                     "username TEXT PRIMARY KEY, birth TEXT, hour TEXT, gender TEXT)")


def get_profile(username):
    """そのユーザーが保存した生年月日（アカウント紐づけ）。無ければ空。"""
    _ensure_profiles()
    with get_conn() as conn:
        r = conn.execute("SELECT birth, hour, gender FROM profiles WHERE username=?",
                         (username,)).fetchone()
    if not r:
        return {"birth": "", "hour": "", "gender": ""}
    return {"birth": r["birth"] or "", "hour": r["hour"] or "", "gender": r["gender"] or ""}


def save_profile(username, birth, hour, gender):
    _ensure_profiles()
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO profiles(username, birth, hour, gender) "
                     "VALUES(?, ?, ?, ?)", (username, birth, hour, gender))


def get_or_create_setting(key, value):
    """無ければ value を入れ、必ず確定値を返す（多重ワーカーでもズレない）。"""
    _ensure_settings()
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)",
                     (key, json.dumps(value)))
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(row["value"])


def _db_path():
    p = os.environ.get("RICARD_DB_PATH", "").strip()
    if p:
        return p
    if os.path.isdir("/var/data"):           # Render の永続ディスク
        return "/var/data/ricard.db"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ricard_local.db")


def _today():
    return datetime.date.today().isoformat()


def _c():
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(_db_path(), check_same_thread=False)
        _conn.execute("PRAGMA busy_timeout=5000")   # 同時書き込みのロック待ち（最大5秒）
        _conn.execute("PRAGMA journal_mode=WAL")     # 読み書きの並行性を上げる
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS daily_spend("
            "date TEXT PRIMARY KEY, jpy REAL NOT NULL DEFAULT 0)")
        _conn.execute(
            "CREATE TABLE IF NOT EXISTS usage("
            "day TEXT, ident TEXT, n INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY(day, ident))")
        _conn.commit()
    return _conn


# ── 当日の利用額（円）──────────────────────────────
def spent_today():
    with _lock:
        row = _c().execute("SELECT jpy FROM daily_spend WHERE date=?", (_today(),)).fetchone()
        return row[0] if row else 0.0


def add_spend(jpy):
    with _lock:
        c = _c()
        c.execute(
            "INSERT INTO daily_spend(date, jpy) VALUES(?, ?) "
            "ON CONFLICT(date) DO UPDATE SET jpy = jpy + ?",
            (_today(), jpy, jpy))
        c.commit()


# ── IP / ユーザー別の当日回数 ────────────────────────
def count_today(ident):
    with _lock:
        row = _c().execute(
            "SELECT n FROM usage WHERE day=? AND ident=?", (_today(), ident)).fetchone()
        return row[0] if row else 0


def bump(ident):
    with _lock:
        c = _c()
        c.execute(
            "INSERT INTO usage(day, ident, n) VALUES(?, ?, 1) "
            "ON CONFLICT(day, ident) DO UPDATE SET n = n + 1",
            (_today(), ident))
        c.commit()
