"""Location router for MemReport."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException

from memreport.models import LocationUpdate, LocationItem, ReportResponse, validate_date_str
from memreport.database import (
    set_report_location,
    delete_report_location,
    get_user_locations,
)
from memreport.auth import get_current_user

router = APIRouter(tags=["locations"])


@router.put("/api/reports/{date}/location", response_model=ReportResponse)
async def update_report_location(
    date: str,
    location_in: LocationUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Set or update GPS coordinates and optional location name for a specific date."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    updated = await set_report_location(
        user_id=current_user["id"],
        date=date,
        latitude=location_in.latitude,
        longitude=location_in.longitude,
        name=location_in.name,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update location")

    return ReportResponse(**updated)


@router.delete("/api/reports/{date}/location")
async def remove_report_location(
    date: str,
    current_user: dict = Depends(get_current_user),
):
    """Remove GPS coordinates from a specific date's report."""
    try:
        validate_date_str(date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    success = await delete_report_location(current_user["id"], date)
    if not success:
        raise HTTPException(status_code=404, detail=f"No report or location found for {date}")

    return {"message": f"Location for {date} removed successfully"}


@router.get("/api/locations", response_model=List[LocationItem])
async def list_locations(current_user: dict = Depends(get_current_user)):
    """List all reports with GPS coordinates for map visualization."""
    locations = await get_user_locations(current_user["id"])
    return [LocationItem(**loc) for loc in locations]
