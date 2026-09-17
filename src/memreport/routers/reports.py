"""Reports router for MemReport."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse

from memreport.models import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportSummary,
    validate_date_str,
)
from memreport.database import (
    get_reports_summary,
    get_report,
    save_report,
    update_report,
    delete_report,
    toggle_report_like,
)
from memreport.auth import get_current_user
from memreport.tts import get_or_create_report_audio, cleanup_report_audio

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("", response_model=List[ReportSummary])
async def list_reports(current_user: dict = Depends(get_current_user)):
    """List all reports with summary metadata for the authenticated user."""
    summaries = await get_reports_summary(current_user["id"])
    return [ReportSummary(**s) for s in summaries]


@router.get("/{date}", response_model=ReportResponse)
async def get_report_by_date(
    date: str,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve full report content and metadata for a specific date (YYYY-MM-DD)."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    report = await get_report(current_user["id"], date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for date {date}")

    return ReportResponse(**report)


@router.post("/{date}", response_model=ReportResponse)
async def create_or_append_report(
    date: str,
    request: Request,
    overwrite: bool = Query(False, description="If true, overwrites existing report; if false, appends"),
    report_in: Optional[ReportCreate] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    Create or append to a daily report.
    Accepts JSON body or raw text/markdown/html body.
    If a report already exists and overwrite=False, content is appended.
    """
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    content = ""
    content_type = "mixed"

    content_type_header = request.headers.get("content-type", "").lower()
    if "application/json" in content_type_header and report_in:
        content = report_in.content
        content_type = report_in.content_type or "mixed"
    else:
        # Check raw body
        raw_body = await request.body()
        if raw_body:
            content = raw_body.decode("utf-8")
            if "text/html" in content_type_header:
                content_type = "html"
            elif "text/markdown" in content_type_header:
                content_type = "markdown"

    if not content:
        raise HTTPException(status_code=400, detail="Report content cannot be empty")

    saved = await save_report(
        user_id=current_user["id"],
        date=date,
        content=content,
        content_type=content_type,
        overwrite=overwrite,
    )
    return ReportResponse(**saved)


@router.put("/{date}", response_model=ReportResponse)
async def edit_report(
    date: str,
    update_in: ReportUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update report text (used by in-viewer editor and direct API updates)."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    updated = await update_report(
        user_id=current_user["id"],
        date=date,
        content=update_in.content,
        content_type=update_in.content_type,
    )
    if not updated:
        # If not existing, create it
        updated = await save_report(
            user_id=current_user["id"],
            date=date,
            content=update_in.content,
            content_type=update_in.content_type or "mixed",
            overwrite=True,
        )

    cleanup_report_audio(current_user["id"], date)
    return ReportResponse(**updated)


@router.delete("/{date}")
async def remove_report(
    date: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete the report for a specific date."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    deleted = await delete_report(current_user["id"], date)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No report found for date {date}")

    cleanup_report_audio(current_user["id"], date)
    return {"message": f"Report for {date} deleted successfully"}


@router.post("/{date}/like")
async def toggle_like(
    date: str,
    current_user: dict = Depends(get_current_user),
):
    """Toggle the like / favorite status for a daily report."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    new_liked = await toggle_report_like(current_user["id"], date)
    if new_liked is None:
        raise HTTPException(status_code=404, detail=f"No report found for date {date}")

    return {"date": date, "is_liked": new_liked}


@router.get("/{date}/audio")
async def get_report_audio(
    date: str,
    lang: str = "de",
    current_user: dict = Depends(get_current_user),
):
    """Serve cached audio (or generate with Google TTS) for the specified report date."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    report = await get_report(current_user["id"], date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report found for date {date}")

    audio_path = await get_or_create_report_audio(
        user_id=current_user["id"],
        date_str=date,
        raw_content=report["content"],
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
