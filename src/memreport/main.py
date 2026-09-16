"""Main FastAPI application for MemReport."""

from contextlib import asynccontextmanager
from pathlib import Path
import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from memreport.config import settings
from memreport.database import init_db, get_user_by_username, create_user
from memreport.auth import hash_password
from memreport.routers import auth, reports, locations, shares, pages

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database schema
    await init_db()

    # Seed default user if not exists
    admin_user = await get_user_by_username(settings.default_admin_user)
    if not admin_user:
        hashed = hash_password(settings.default_admin_password)
        await create_user(settings.default_admin_user, hashed, is_admin=True)
        print(f"[MemReport] Initialized default admin user '{settings.default_admin_user}'")
    elif not admin_user.get("is_admin"):
        from memreport.database import get_db
        async with get_db() as db:
            await db.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (settings.default_admin_user,))
            await db.commit()

    yield


app = FastAPI(
    title="MemReport API",
    description="Daily report hub with calendar viewer, maps, mixed markdown/html, and share links",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth.router)
app.include_router(reports.router)
app.include_router(locations.router)
app.include_router(shares.router)
app.include_router(pages.router)


def start():
    """Entry point for CLI command."""
    uvicorn.run("memreport.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    start()
