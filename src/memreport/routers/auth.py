"""Authentication router for MemReport."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status

from memreport.config import settings
from memreport.models import UserCreate, UserResponse, Token
from memreport.database import create_user, get_user_by_username
from memreport.auth import hash_password, verify_password, create_access_token, get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate):
    existing = await get_user_by_username(user_in.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )
    pw_hash = hash_password(user_in.password)
    user_id = await create_user(user_in.username, pw_hash)
    if not user_id:
        raise HTTPException(status_code=500, detail="Failed to create user")
    user = await get_user_by_username(user_in.username)
    return UserResponse(
        id=user["id"],
        username=user["username"],
        created_at=user["created_at"],
    )


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    user_in: Optional[UserCreate] = None,
):
    username = None
    password = None

    content_type = request.headers.get("content-type", "").lower()
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        form = await request.form()
        username = form.get("username")
        password = form.get("password")
    elif user_in:
        username = user_in.username
        password = user_in.password
    else:
        try:
            body = await request.json()
            username = body.get("username")
            password = body.get("password")
        except Exception:
            pass

    if not username or not password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username and password are required",
        )

    user = await get_user_by_username(username)
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    token = create_access_token(data={"sub": user["username"]})

    # Set HTTP-only cookie for web browser session
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False,  # Set to True in production with HTTPS
    )

    return Token(access_token=token, token_type="bearer", username=user["username"])


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        created_at=current_user["created_at"],
    )
