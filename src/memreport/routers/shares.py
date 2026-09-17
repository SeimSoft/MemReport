"""Shares router for MemReport."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from memreport.config import settings
from memreport.tts import get_or_create_report_audio
from memreport.models import (
    ShareCreate,
    ShareUpdate,
    ShareResponse,
    PublicShareData,
    ReportResponse,
)
from memreport.database import (
    create_share,
    update_share,
    get_user_shares,
    delete_share,
    get_share_by_token,
)
from memreport.auth import get_current_user

router = APIRouter(tags=["shares"])


def get_base_url(request: Request) -> str:
    """Resolve base URL taking into account config, proxy headers and request."""
    if settings.base_url:
        return settings.base_url.rstrip("/")

    # Respect standard proxy forwarding headers if present
    forwarded_proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    forwarded_prefix = request.headers.get("x-forwarded-prefix", "").strip("/")

    if forwarded_host:
        prefix_part = f"/{forwarded_prefix}" if forwarded_prefix else ""
        return f"{forwarded_proto}://{forwarded_host}{prefix_part}"

    return str(request.base_url).rstrip("/")


@router.post("/api/shares", response_model=ShareResponse)
async def create_share_link(
    share_in: ShareCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Generate a public shareable link for one or more dates or all reports."""
    token = secrets.token_urlsafe(18)
    expires_at = None
    if share_in.expires_in_days:
        expires_at = (
            datetime.now(timezone.utc) + timedelta(days=share_in.expires_in_days)
        ).isoformat()

    created = await create_share(
        user_id=current_user["id"],
        token=token,
        dates=share_in.dates,
        title=share_in.title,
        share_all=share_in.share_all,
        expires_at=expires_at,
    )

    base_url = get_base_url(request)
    share_url = f"{base_url}/share/{token}"

    return ShareResponse(
        id=created["id"],
        token=created["token"],
        dates=created["dates"],
        title=created["title"],
        share_all=created["share_all"],
        share_url=share_url,
        created_at=created["created_at"],
        expires_at=created["expires_at"],
    )


@router.get("/api/shares", response_model=List[ShareResponse])
async def list_user_shares(
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """List all created share links for the logged-in user."""
    shares = await get_user_shares(current_user["id"])
    base_url = get_base_url(request)
    result = []
    for s in shares:
        share_url = f"{base_url}/share/{s['token']}"
        result.append(
            ShareResponse(
                id=s["id"],
                token=s["token"],
                dates=s["dates"],
                title=s["title"],
                share_all=s.get("share_all", False),
                share_url=share_url,
                created_at=s["created_at"],
                expires_at=s["expires_at"],
            )
        )
    return result


@router.put("/api/shares/{share_id}", response_model=ShareResponse)
async def update_share_link(
    share_id: int,
    share_in: ShareUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Update an existing share link's title, dates, share_all flag, or expiry."""
    expires_at = None
    if share_in.expires_in_days is not None:
        if share_in.expires_in_days > 0:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(days=share_in.expires_in_days)
            ).isoformat()
        else:
            expires_at = None

    updated = await update_share(
        user_id=current_user["id"],
        share_id=share_id,
        title=share_in.title,
        dates=share_in.dates,
        share_all=share_in.share_all,
        expires_at=expires_at,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Share not found")

    base_url = get_base_url(request)
    share_url = f"{base_url}/share/{updated['token']}"

    return ShareResponse(
        id=updated["id"],
        token=updated["token"],
        dates=updated["dates"],
        title=updated["title"],
        share_all=updated["share_all"],
        share_url=share_url,
        created_at=updated["created_at"],
        expires_at=updated["expires_at"],
    )


@router.delete("/api/shares/{share_id}")
async def revoke_share_link(
    share_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Revoke/delete an existing share link."""
    success = await delete_share(current_user["id"], share_id)
    if not success:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"message": "Share link revoked successfully"}


@router.get("/api/public/shares/{token}", response_model=PublicShareData)
async def get_public_share(token: str):
    """
    Public API endpoint to retrieve reports associated with a share token.
    No credentials/authentication required.
    """
    share = await get_share_by_token(token)
    if not share:
        raise HTTPException(status_code=404, detail="Shared report not found or link expired")

    reports_map = {}
    for d, rep in share["reports"].items():
        reports_map[d] = ReportResponse(**rep)

    return PublicShareData(
        title=share["title"],
        dates=share["dates"],
        share_all=share.get("share_all", False),
        reports=reports_map,
        expires_at=share["expires_at"],
    )


@router.get("/api/public/shares/{token}/reports/{date}/audio")
async def get_public_share_report_audio(token: str, date: str, lang: str = "de"):
    """Public audio stream for a report contained within a shared link."""
    share = await get_share_by_token(token)
    if not share:
        raise HTTPException(status_code=404, detail="Shared report not found or link expired")

    report_dict = share["reports"].get(date)
    if not report_dict:
        raise HTTPException(status_code=404, detail="Report for date not included in this share")

    audio_path = await get_or_create_report_audio(
        user_id=report_dict["user_id"],
        date_str=date,
        raw_content=report_dict["content"],
        lang=lang,
    )
    if not audio_path or not audio_path.exists():
        raise HTTPException(status_code=400, detail="Kein lesbarer Text im Bericht vorhanden")

    return FileResponse(
        audio_path,
        media_type="audio/mpeg",
        filename=f"report-{date}.mp3",
        headers={"Cache-Control": "public, max-age=86400"},
    )

