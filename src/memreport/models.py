"""Pydantic models for MemReport."""

from typing import Optional, List, Dict
from pydantic import BaseModel, Field, field_validator
import re

DATE_REGEX = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def validate_date_str(v: str) -> str:
    if not DATE_REGEX.match(v):
        raise ValueError("Date must be in YYYY-MM-DD format")
    return v


class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)


class UserCreate(UserBase):
    password: str = Field(..., min_length=4)
    is_admin: Optional[bool] = False


class UserUpdate(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_username: Optional[str] = Field(None, min_length=2, max_length=50)
    new_password: Optional[str] = Field(None, min_length=4)


class UserResponse(UserBase):
    id: int
    is_admin: bool = False
    created_at: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class TokenData(BaseModel):
    username: Optional[str] = None


class ReportCreate(BaseModel):
    content: str
    content_type: Optional[str] = "mixed"  # "markdown", "html", or "mixed"


class ReportUpdate(BaseModel):
    content: str
    content_type: Optional[str] = None


class LocationUpdate(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    name: Optional[str] = Field(None, max_length=120)


class ReportResponse(BaseModel):
    id: int
    date: str
    content_type: str
    content: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    is_liked: bool = False
    created_at: str
    updated_at: str


class ReportSummary(BaseModel):
    date: str
    content_type: str
    has_location: bool
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    location_name: Optional[str] = None
    is_liked: bool = False
    size_bytes: int
    updated_at: str


class LocationItem(BaseModel):
    date: str
    latitude: float
    longitude: float
    location_name: Optional[str] = None
    snippet: str
    content_type: str


class ShareCreate(BaseModel):
    dates: List[str] = Field(..., min_length=1)
    title: Optional[str] = Field(None, max_length=150)
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)

    @field_validator("dates")
    @classmethod
    def validate_dates(cls, dates: List[str]) -> List[str]:
        for d in dates:
            validate_date_str(d)
        return sorted(list(set(dates)))


class ShareResponse(BaseModel):
    id: int
    token: str
    dates: List[str]
    title: Optional[str] = None
    share_url: str
    created_at: str
    expires_at: Optional[str] = None


class PublicShareData(BaseModel):
    title: Optional[str] = None
    dates: List[str]
    reports: Dict[str, ReportResponse]
    expires_at: Optional[str] = None
