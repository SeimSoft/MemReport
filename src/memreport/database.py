"""Database access layer using aiosqlite for MemReport."""

from contextlib import asynccontextmanager
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
import aiosqlite

from memreport.config import settings


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(settings.db_path) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA foreign_keys = ON")
        yield conn


async def init_db() -> None:
    async with get_db() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                date TEXT NOT NULL,
                content_type TEXT NOT NULL DEFAULT 'mixed',
                content TEXT NOT NULL,
                latitude REAL,
                longitude REAL,
                location_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, date)
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_reports_user_date ON reports(user_id, date)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shares (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token TEXT UNIQUE NOT NULL,
                dates TEXT NOT NULL,
                title TEXT,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_shares_token ON shares(token)
        """)
        await db.commit()


# --- User Queries ---

async def create_user(username: str, password_hash: str) -> Optional[int]:
    now = utc_now_iso()
    async with get_db() as db:
        try:
            cursor = await db.execute(
                "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
                (username, password_hash, now),
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, username, password_hash, created_at FROM users WHERE username = ?",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, username, created_at FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# --- Report Queries ---

def _format_append(existing_content: str, new_content: str, content_type: str) -> str:
    """Appends new report content to existing content gracefully."""
    existing_content = existing_content.rstrip()
    new_content = new_content.strip()
    if not existing_content:
        return new_content
    if not new_content:
        return existing_content

    if content_type == "html" and "</body>" in existing_content:
        # Insert before closing </body> if present
        sep = '<hr class="report-divider my-6" />\n'
        return existing_content.replace("</body>", f"{sep}{new_content}\n</body>")

    # Default for markdown and mixed
    return f"{existing_content}\n\n---\n\n{new_content}"


async def save_report(
    user_id: int,
    date: str,
    content: str,
    content_type: str = "mixed",
    overwrite: bool = False,
) -> Dict[str, Any]:
    now = utc_now_iso()
    async with get_db() as db:
        async with db.execute(
            "SELECT id, content, content_type, latitude, longitude, location_name, created_at FROM reports WHERE user_id = ? AND date = ?",
            (user_id, date),
        ) as cursor:
            existing = await cursor.fetchone()

        if existing:
            if overwrite:
                final_content = content
                final_type = content_type or existing["content_type"]
            else:
                final_type = existing["content_type"]
                final_content = _format_append(existing["content"], content, final_type)

            await db.execute(
                """
                UPDATE reports
                SET content = ?, content_type = ?, updated_at = ?
                WHERE user_id = ? AND date = ?
                """,
                (final_content, final_type, now, user_id, date),
            )
            await db.commit()
            return await get_report(user_id, date)
        else:
            await db.execute(
                """
                INSERT INTO reports (user_id, date, content_type, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, date, content_type, content, now, now),
            )
            await db.commit()
            return await get_report(user_id, date)


async def update_report(
    user_id: int,
    date: str,
    content: str,
    content_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = utc_now_iso()
    async with get_db() as db:
        if content_type:
            cursor = await db.execute(
                """
                UPDATE reports
                SET content = ?, content_type = ?, updated_at = ?
                WHERE user_id = ? AND date = ?
                """,
                (content, content_type, now, user_id, date),
            )
        else:
            cursor = await db.execute(
                """
                UPDATE reports
                SET content = ?, updated_at = ?
                WHERE user_id = ? AND date = ?
                """,
                (content, now, user_id, date),
            )
        await db.commit()
        if cursor.rowcount == 0:
            return None
    return await get_report(user_id, date)


async def get_report(user_id: int, date: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, date, content_type, content, latitude, longitude, location_name, created_at, updated_at
            FROM reports
            WHERE user_id = ? AND date = ?
            """,
            (user_id, date),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_reports_summary(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT date, content_type,
                   (latitude IS NOT NULL AND longitude IS NOT NULL) as has_location,
                   latitude, longitude, location_name,
                   LENGTH(content) as size_bytes,
                   updated_at
            FROM reports
            WHERE user_id = ?
            ORDER BY date DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def delete_report(user_id: int, date: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM reports WHERE user_id = ? AND date = ?",
            (user_id, date),
        )
        await db.commit()
        return cursor.rowcount > 0


# --- Location Queries ---

async def set_report_location(
    user_id: int,
    date: str,
    latitude: float,
    longitude: float,
    name: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    now = utc_now_iso()
    async with get_db() as db:
        # Check if report exists
        cursor = await db.execute(
            """
            UPDATE reports
            SET latitude = ?, longitude = ?, location_name = ?, updated_at = ?
            WHERE user_id = ? AND date = ?
            """,
            (latitude, longitude, name, now, user_id, date),
        )
        await db.commit()
        if cursor.rowcount == 0:
            # Create an initial empty report if it does not exist yet
            await db.execute(
                """
                INSERT INTO reports (user_id, date, content_type, content, latitude, longitude, location_name, created_at, updated_at)
                VALUES (?, ?, 'mixed', '', ?, ?, ?, ?, ?)
                """,
                (user_id, date, latitude, longitude, name, now, now),
            )
            await db.commit()
    return await get_report(user_id, date)


async def delete_report_location(user_id: int, date: str) -> bool:
    now = utc_now_iso()
    async with get_db() as db:
        cursor = await db.execute(
            """
            UPDATE reports
            SET latitude = NULL, longitude = NULL, location_name = NULL, updated_at = ?
            WHERE user_id = ? AND date = ?
            """,
            (now, user_id, date),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_user_locations(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT date, latitude, longitude, location_name, content_type,
                   SUBSTR(content, 1, 140) as snippet
            FROM reports
            WHERE user_id = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY date DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# --- Share Queries ---

async def create_share(
    user_id: int,
    token: str,
    dates: List[str],
    title: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> Dict[str, Any]:
    now = utc_now_iso()
    dates_json = json.dumps(dates)
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO shares (user_id, token, dates, title, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, token, dates_json, title, now, expires_at),
        )
        await db.commit()
        share_id = cursor.lastrowid
        return {
            "id": share_id,
            "token": token,
            "dates": dates,
            "title": title,
            "created_at": now,
            "expires_at": expires_at,
        }


async def get_user_shares(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, token, dates, title, created_at, expires_at
            FROM shares
            WHERE user_id = ?
            ORDER BY created_at DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            result = []
            for r in rows:
                item = dict(r)
                item["dates"] = json.loads(item["dates"])
                result.append(item)
            return result


async def delete_share(user_id: int, share_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "DELETE FROM shares WHERE user_id = ? AND id = ?",
            (user_id, share_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def get_share_by_token(token: str) -> Optional[Dict[str, Any]]:
    now = utc_now_iso()
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, user_id, token, dates, title, created_at, expires_at
            FROM shares
            WHERE token = ?
            """,
            (token,),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            share = dict(row)

            # Check expiration
            if share["expires_at"] and share["expires_at"] < now:
                return None

            dates = json.loads(share["dates"])
            user_id = share["user_id"]

            # Fetch the actual reports for these dates
            reports_dict = {}
            if dates:
                placeholders = ",".join(["?"] * len(dates))
                async with db.execute(
                    f"""
                    SELECT id, date, content_type, content, latitude, longitude, location_name, created_at, updated_at
                    FROM reports
                    WHERE user_id = ? AND date IN ({placeholders})
                    ORDER BY date ASC
                    """,
                    [user_id] + dates,
                ) as rep_cursor:
                    rep_rows = await rep_cursor.fetchall()
                    for rep in rep_rows:
                        reports_dict[rep["date"]] = dict(rep)

            return {
                "id": share["id"],
                "token": share["token"],
                "title": share["title"],
                "dates": dates,
                "reports": reports_dict,
                "created_at": share["created_at"],
                "expires_at": share["expires_at"],
            }
