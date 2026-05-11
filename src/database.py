"""SQLite storage: subscribers, last-state, and check history."""
from __future__ import annotations

import aiosqlite

from .config import DB_PATH


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                chat_id INTEGER PRIMARY KEY,
                username TEXT,
                subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1
            );

            CREATE TABLE IF NOT EXISTS last_state (
                key TEXT PRIMARY KEY,
                value TEXT
            );

            CREATE TABLE IF NOT EXISTS check_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                account_name TEXT,
                available INTEGER,
                message TEXT,
                duration_ms INTEGER
            );

            CREATE INDEX IF NOT EXISTS idx_check_history_time
                ON check_history(checked_at DESC);
            """
        )
        await db.commit()


# ---- subscribers ----

async def add_subscriber(chat_id: int, username: str | None) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT active FROM subscribers WHERE chat_id = ?", (chat_id,))
        row = await cur.fetchone()
        if row and row[0] == 1:
            return False
        await db.execute(
            """
            INSERT INTO subscribers (chat_id, username, active)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id) DO UPDATE SET active = 1, username = excluded.username
            """,
            (chat_id, username or ""),
        )
        await db.commit()
        return True


async def remove_subscriber(chat_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("UPDATE subscribers SET active = 0 WHERE chat_id = ?", (chat_id,))
        await db.commit()
        return cur.rowcount > 0


async def get_active_subscribers() -> list[int]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT chat_id FROM subscribers WHERE active = 1")
        rows = await cur.fetchall()
        return [r[0] for r in rows]


async def count_active() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM subscribers WHERE active = 1")
        row = await cur.fetchone()
        return row[0] if row else 0


async def list_subscribers(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT chat_id, username, subscribed_at, active
            FROM subscribers ORDER BY subscribed_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ---- last state ----

async def get_state(key: str) -> str | None:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT value FROM last_state WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else None


async def set_state(key: str, value: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO last_state (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        await db.commit()


# ---- check history ----

async def record_check(account_name: str, available: bool, message: str, duration_ms: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO check_history (account_name, available, message, duration_ms)
            VALUES (?, ?, ?, ?)
            """,
            (account_name, 1 if available else 0, message, duration_ms),
        )
        await db.commit()


async def recent_checks(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT checked_at, account_name, available, message, duration_ms
            FROM check_history ORDER BY checked_at DESC LIMIT ?
            """,
            (limit,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def check_stats(hours: int = 24) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            f"""
            SELECT
                COUNT(*) AS total,
                SUM(available) AS hits,
                AVG(duration_ms) AS avg_ms
            FROM check_history
            WHERE checked_at >= datetime('now', '-{int(hours)} hours')
            """
        )
        row = await cur.fetchone()
        return {
            "total": row[0] or 0,
            "hits": row[1] or 0,
            "avg_ms": int(row[2] or 0),
            "hours": hours,
        }
