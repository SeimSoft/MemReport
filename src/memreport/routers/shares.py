"""Shares router for MemReport."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request

from memreport.models import (
    ShareCreate,
    ShareResponse,
    PublicShareData,
    ReportResponse,
)
from memreport.database import (
    create_share,
    get_user_shares,
    delete_share,
    get_share_by_token,
)
from memreport.auth import get_current_user

router = APIRouter(tags=["shares"])


@router.post("/api/shares", response_model=ShareResponse)
async def create_share_link(
    share_in: ShareCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Generate a public shareable link for one or more dates."""
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
        expires_at=expires_at,
    )

    base_url = str(request.base_url).rstrip("/")
    share_url = f"{base_url}/share/{token}"

    return ShareResponse(
        id=created["id"],
        token=created["token"],
        dates=created["dates"],
        title=created["title"],
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
    base_url = str(request.base_url).rstrip("/")
    result = []
    for s in shares:
        share_url = f"{base_url}/share/{s['token']}"
        result.append(
            ShareResponse(
                id=s["id"],
                token=s["token"],
                dates=s["dates"],
                title=s["title"],
                share_url=share_url,
                created_at=s["created_at"],
                expires_at=s["expires_at"],
            )
        )
    return result


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
        reports=reports_map,
        expires_at=share["expires_at"],
    )
