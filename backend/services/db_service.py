"""
db_service.py
-------------
SQLite logging for all traffic readings.
Tables:
  - traffic_log : every status reading (simulation + video)
  - spiderweb_log : per-node congestion snapshots
"""

import sqlite3
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "traffic.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist. Call once at app startup."""
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS traffic_log (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    NOT NULL,
                mode            TEXT    NOT NULL,
                vehicle_count   INTEGER,
                congestion      TEXT,
                future_cong     TEXT,
                green_time      INTEGER
            );

            CREATE TABLE IF NOT EXISTS spiderweb_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp   TEXT    NOT NULL,
                node        TEXT    NOT NULL,
                congestion  INTEGER NOT NULL
            );
        """)
    print("✅ DB initialised at", DB_PATH)


# ── write ──────────────────────────────────────────────
def log_traffic(mode, vehicle_count, congestion, future_cong, green_time):
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO traffic_log
               (timestamp, mode, vehicle_count, congestion, future_cong, green_time)
               VALUES (?,?,?,?,?,?)""",
            (ts, mode, vehicle_count, congestion, future_cong, green_time)
        )


def log_spiderweb(node_data: dict):
    """node_data = {node_name: congestion_value, ...}"""
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO spiderweb_log (timestamp, node, congestion) VALUES (?,?,?)",
            [(ts, node, val) for node, val in node_data.items()]
        )


# ── read ───────────────────────────────────────────────
def get_recent_traffic(limit=30):
    """Last N traffic readings, newest first."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT timestamp, mode, vehicle_count, congestion,
                      future_cong, green_time
               FROM traffic_log
               ORDER BY id DESC LIMIT ?""",
            (limit,)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_spiderweb_history(node, limit=20):
    """Congestion history for a specific node."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT timestamp, congestion FROM spiderweb_log
               WHERE node=? ORDER BY id DESC LIMIT ?""",
            (node, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_daily_summary():
    """Hourly average vehicle count for today."""
    today = time.strftime("%Y-%m-%d")
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT strftime('%H', timestamp) as hour,
                      AVG(vehicle_count) as avg_count,
                      COUNT(*) as readings
               FROM traffic_log
               WHERE timestamp LIKE ? AND vehicle_count IS NOT NULL
               GROUP BY hour ORDER BY hour""",
            (today + "%",)
        ).fetchall()
    return [dict(r) for r in rows]
