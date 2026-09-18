"""Database access layer using aiosqlite for MemReport."""

from contextlib import asynccontextmanager
import json
import re
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
                is_admin INTEGER NOT NULL DEFAULT 0,
                theme TEXT NOT NULL DEFAULT 'dark',
                created_at TEXT NOT NULL
            )
        """)
        # Migration for existing users table
        try:
            await db.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE users ADD COLUMN theme TEXT NOT NULL DEFAULT 'dark'")
        except Exception:
            pass

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
                is_liked INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(user_id, date)
            )
        """)
        # Migration for existing reports table (is_liked)
        try:
            await db.execute("ALTER TABLE reports ADD COLUMN is_liked INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
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
                share_all INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                expires_at TEXT
            )
        """)
        try:
            await db.execute("ALTER TABLE shares ADD COLUMN share_all INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_shares_token ON shares(token)
        """)
        await db.commit()


# --- User Queries ---

async def create_user(username: str, password_hash: str, is_admin: bool = False, theme: str = "dark") -> Optional[int]:
    now = utc_now_iso()
    async with get_db() as db:
        try:
            cursor = await db.execute(
                "INSERT INTO users (username, password_hash, is_admin, theme, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, 1 if is_admin else 0, theme, now),
            )
            await db.commit()
            return cursor.lastrowid
        except aiosqlite.IntegrityError:
            return None


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, username, password_hash, is_admin, theme, created_at FROM users WHERE username = ?",
            (username,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, username, password_hash, is_admin, theme, created_at FROM users WHERE id = ?",
            (user_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_all_users() -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, username, is_admin, theme, created_at FROM users ORDER BY id ASC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def update_user_theme(user_id: int, theme: str) -> bool:
    async with get_db() as db:
        cursor = await db.execute(
            "UPDATE users SET theme = ? WHERE id = ?",
            (theme, user_id),
        )
        await db.commit()
        return cursor.rowcount > 0


async def delete_user_by_id(user_id: int) -> bool:
    async with get_db() as db:
        cursor = await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        return cursor.rowcount > 0


async def update_user(
    user_id: int,
    new_username: Optional[str] = None,
    new_password_hash: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        if new_username and new_password_hash:
            await db.execute(
                "UPDATE users SET username = ?, password_hash = ? WHERE id = ?",
                (new_username, new_password_hash, user_id),
            )
        elif new_username:
            await db.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, user_id),
            )
        elif new_password_hash:
            await db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (new_password_hash, user_id),
            )
        await db.commit()
    return await get_user_by_id(user_id)


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
            SELECT id, date, content_type, content, latitude, longitude, location_name,
                   is_liked, created_at, updated_at
            FROM reports
            WHERE user_id = ? AND date = ?
            """,
            (user_id, date),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["is_liked"] = bool(data.get("is_liked", 0))
            return data


async def get_reports_summary(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT date, content_type,
                   (latitude IS NOT NULL AND longitude IS NOT NULL) as has_location,
                   latitude, longitude, location_name,
                   is_liked,
                   LENGTH(content) as size_bytes,
                   updated_at
            FROM reports
            WHERE user_id = ?
            ORDER BY date DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["is_liked"] = bool(item.get("is_liked", 0))
                results.append(item)
            return results


async def toggle_report_like(user_id: int, date: str) -> Optional[bool]:
    """Toggle like status for a report. Returns new is_liked state, or None if report does not exist."""
    now = utc_now_iso()
    async with get_db() as db:
        async with db.execute(
            "SELECT is_liked FROM reports WHERE user_id = ? AND date = ?",
            (user_id, date),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            current_liked = bool(row["is_liked"])

        new_liked = not current_liked
        await db.execute(
            "UPDATE reports SET is_liked = ?, updated_at = ? WHERE user_id = ? AND date = ?",
            (1 if new_liked else 0, now, user_id, date),
        )
        await db.commit()
        return new_liked


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


def extract_routes_from_markdown(content: str) -> List[Dict[str, Any]]:
    """
    Extract GPS route objects from ```leaflet or ```geojson code blocks.
    Returns list of dicts with title, coordinates, distance_km, elevation_gain_m.
    """
    routes = []
    if not content:
        return routes

    pattern = re.compile(r"```(?:leaflet|geojson)\s*\n([\s\S]*?)\n```", re.IGNORECASE)
    for match in pattern.finditer(content):
        raw_json = match.group(1).strip()
        try:
            data = json.loads(raw_json)
            if isinstance(data, dict):
                coords = data.get("coordinates")
                if isinstance(coords, list) and len(coords) > 0:
                    if isinstance(coords[0], (list, tuple)) and len(coords[0]) >= 2:
                        routes.append({
                            "title": data.get("title") or "GPS Route",
                            "coordinates": coords,
                            "distance_km": data.get("distance_km"),
                            "elevation_gain_m": data.get("elevation_gain_m"),
                        })
                elif data.get("type") in ("FeatureCollection", "Feature", "LineString"):
                    geo_coords = []
                    if data.get("type") == "LineString":
                        geo_coords = [[pt[1], pt[0]] for pt in data.get("coordinates", []) if len(pt) >= 2]
                    elif data.get("type") == "Feature" and data.get("geometry", {}).get("type") == "LineString":
                        geo_coords = [[pt[1], pt[0]] for pt in data["geometry"].get("coordinates", []) if len(pt) >= 2]
                    if geo_coords:
                        routes.append({
                            "title": data.get("properties", {}).get("title") or "GPS Route",
                            "coordinates": geo_coords,
                            "distance_km": data.get("properties", {}).get("distance_km"),
                            "elevation_gain_m": data.get("properties", {}).get("elevation_gain_m"),
                        })
        except Exception:
            continue
    return routes


async def get_user_locations(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT date, latitude, longitude, location_name, content_type,
                   content
            FROM reports
            WHERE user_id = ?
            ORDER BY date DESC
            """,
            (user_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                content = item.pop("content", "") or ""
                routes = extract_routes_from_markdown(content)

                if (item["latitude"] is None or item["longitude"] is None) and routes:
                    first_coord = routes[0]["coordinates"][0]
                    item["latitude"] = float(first_coord[0])
                    item["longitude"] = float(first_coord[1])
                    if not item.get("location_name"):
                        item["location_name"] = routes[0].get("title") or "Route"

                if item["latitude"] is not None and item["longitude"] is not None:
                    item["snippet"] = content[:140] if content else ""
                    item["routes"] = routes if routes else None
                    results.append(item)
            return results


# --- Share Queries ---

async def create_share(
    user_id: int,
    token: str,
    dates: List[str],
    title: Optional[str] = None,
    share_all: bool = False,
    expires_at: Optional[str] = None,
) -> Dict[str, Any]:
    now = utc_now_iso()
    dates_json = json.dumps(dates)
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO shares (user_id, token, dates, title, share_all, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, token, dates_json, title, 1 if share_all else 0, now, expires_at),
        )
        await db.commit()
        share_id = cursor.lastrowid
        return {
            "id": share_id,
            "token": token,
            "dates": dates,
            "title": title,
            "share_all": bool(share_all),
            "created_at": now,
            "expires_at": expires_at,
        }


async def update_share(
    user_id: int,
    share_id: int,
    title: Optional[str] = None,
    dates: Optional[List[str]] = None,
    share_all: Optional[bool] = None,
    expires_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            "SELECT id, token, dates, title, share_all, created_at, expires_at FROM shares WHERE user_id = ? AND id = ?",
            (user_id, share_id),
        ) as cursor:
            row = await cursor.fetchone()
            if not row:
                return None
            current = dict(row)

        new_title = title if title is not None else current["title"]
        new_dates = dates if dates is not None else json.loads(current["dates"])
        new_share_all = (1 if share_all else 0) if share_all is not None else current.get("share_all", 0)
        new_expires_at = expires_at if expires_at is not None else current["expires_at"]

        await db.execute(
            """
            UPDATE shares
            SET title = ?, dates = ?, share_all = ?, expires_at = ?
            WHERE user_id = ? AND id = ?
            """,
            (new_title, json.dumps(new_dates), new_share_all, new_expires_at, user_id, share_id),
        )
        await db.commit()

        return {
            "id": share_id,
            "token": current["token"],
            "dates": new_dates,
            "title": new_title,
            "share_all": bool(new_share_all),
            "created_at": current["created_at"],
            "expires_at": new_expires_at,
        }


async def get_user_shares(user_id: int) -> List[Dict[str, Any]]:
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, token, dates, title, share_all, created_at, expires_at
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
                item["share_all"] = bool(item.get("share_all", 0))
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
            SELECT id, user_id, token, dates, title, share_all, created_at, expires_at
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

            user_id = share["user_id"]
            is_share_all = bool(share.get("share_all", 0))

            reports_dict = {}
            if is_share_all:
                # Fetch ALL reports for this user (including future ones)
                async with db.execute(
                    """
                    SELECT id, date, content_type, content, latitude, longitude, location_name, created_at, updated_at
                    FROM reports
                    WHERE user_id = ?
                    ORDER BY date ASC
                    """,
                    (user_id,),
                ) as rep_cursor:
                    rep_rows = await rep_cursor.fetchall()
                    for rep in rep_rows:
                        item = dict(rep)
                        if (item["latitude"] is None or item["longitude"] is None) and item.get("content"):
                            routes = extract_routes_from_markdown(item["content"])
                            if routes:
                                first_pt = routes[0]["coordinates"][0]
                                item["latitude"] = float(first_pt[0])
                                item["longitude"] = float(first_pt[1])
                                if not item.get("location_name"):
                                    item["location_name"] = routes[0].get("title") or "Route"
                        reports_dict[item["date"]] = item
                dates = list(reports_dict.keys())
            else:
                dates = json.loads(share["dates"])
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
                            item = dict(rep)
                            if (item["latitude"] is None or item["longitude"] is None) and item.get("content"):
                                routes = extract_routes_from_markdown(item["content"])
                                if routes:
                                    first_pt = routes[0]["coordinates"][0]
                                    item["latitude"] = float(first_pt[0])
                                    item["longitude"] = float(first_pt[1])
                                    if not item.get("location_name"):
                                        item["location_name"] = routes[0].get("title") or "Route"
                            reports_dict[item["date"]] = item

            return {
                "id": share["id"],
                "token": share["token"],
                "title": share["title"],
                "dates": dates,
                "share_all": is_share_all,
                "reports": reports_dict,
                "created_at": share["created_at"],
                "expires_at": share["expires_at"],
            }
