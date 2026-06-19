# -*- coding: utf-8 -*-
"""固い保存役 — 永続ディスク上の SQLite に「当日の利用額」「IP/ユーザー別の回数」を記録。

再起動・再デプロイ・多重ワーカーでも消えない＝本物の固い上限の土台。
保存先は永続ディスク（Renderでは /var/data）。ローカルでは作業フォルダ内のファイル。
"""

import os
import sqlite3
import datetime
import threading

_lock = threading.Lock()
_conn = None


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
