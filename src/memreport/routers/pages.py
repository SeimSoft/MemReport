"""Web page rendering router for MemReport."""

from pathlib import Path
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from memreport.auth import get_current_user_optional
from memreport.database import get_share_by_token

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    current_user: dict = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/viewer", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    current_user: dict = Depends(get_current_user_optional),
):
    if current_user:
        return RedirectResponse(url="/viewer", status_code=302)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={},
    )


@router.get("/logout")
async def logout_page():
    res = RedirectResponse(url="/login", status_code=302)
    res.delete_cookie(key="access_token", path="/")
    return res


@router.get("/viewer", response_class=HTMLResponse)
async def viewer_page(
    request: Request,
    current_user: dict = Depends(get_current_user_optional),
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=302)
    from memreport.config import settings
    is_admin = bool(current_user.get("is_admin")) or (current_user["username"] == settings.default_admin_user)
    return templates.TemplateResponse(
        request=request,
        name="viewer.html",
        context={
            "username": current_user["username"],
            "user_id": current_user["id"],
            "is_admin": is_admin,
        },
    )


@router.get("/share/{token}", response_class=HTMLResponse)
async def public_share_page(request: Request, token: str):
    share = await get_share_by_token(token)
    if not share:
        return templates.TemplateResponse(
            request=request,
            name="share_error.html",
            context={
                "message": "Dieser Freigabe-Link existiert nicht oder ist abgelaufen.",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        request=request,
        name="share.html",
        context={
            "token": token,
            "title": share["title"] or "Geteilte Berichte",
            "dates": share["dates"],
            "expires_at": share["expires_at"],
        },
    )
