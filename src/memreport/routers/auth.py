from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status

from memreport.config import settings
from memreport.models import UserCreate, UserUpdate, UserResponse, Token
from memreport.database import (
    create_user,
    get_user_by_username,
    get_user_by_id,
    get_all_users,
    delete_user_by_id,
    update_user,
)
from memreport.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    require_admin,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_in: UserCreate,
    current_admin: dict = Depends(require_admin),
):
    """Register a new user account. Restricted to administrators only."""
    existing = await get_user_by_username(user_in.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dieser Benutzername ist bereits vergeben.",
        )
    pw_hash = hash_password(user_in.password)
    user_id = await create_user(user_in.username, pw_hash, is_admin=bool(user_in.is_admin))
    if not user_id:
        raise HTTPException(status_code=500, detail="Benutzer konnte nicht erstellt werden.")
    user = await get_user_by_id(user_id)
    return UserResponse(
        id=user["id"],
        username=user["username"],
        is_admin=bool(user.get("is_admin", 0)),
        created_at=user["created_at"],
    )


@router.get("/users", response_model=List[UserResponse])
async def list_users(current_admin: dict = Depends(require_admin)):
    """List all users. Restricted to administrators only."""
    users = await get_all_users()
    return [
        UserResponse(
            id=u["id"],
            username=u["username"],
            is_admin=bool(u.get("is_admin", 0)),
            created_at=u["created_at"],
        )
        for u in users
    ]


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_admin: dict = Depends(require_admin),
):
    """Delete a user account. Cannot delete self. Restricted to administrators only."""
    if user_id == current_admin["id"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administratoren können das eigene Konto nicht löschen.",
        )
    success = await delete_user_by_id(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden.")
    return {"message": "Benutzer erfolgreich gelöscht."}


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
@router.get("/logout")
async def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    is_admin = bool(current_user.get("is_admin")) or (current_user["username"] == settings.default_admin_user)
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        is_admin=is_admin,
        created_at=current_user["created_at"],
    )


@router.put("/me", response_model=UserResponse)
async def update_profile(
    user_update: UserUpdate,
    response: Response,
    current_user: dict = Depends(get_current_user),
):
    """Update current user username and/or password."""
    # Verify current password
    if not verify_password(user_update.current_password, current_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Das aktuelle Passwort ist nicht korrekt",
        )

    new_username = None
    if user_update.new_username and user_update.new_username != current_user["username"]:
        existing = await get_user_by_username(user_update.new_username)
        if existing and existing["id"] != current_user["id"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Dieser Benutzername ist bereits vergeben",
            )
        new_username = user_update.new_username

    new_hash = None
    if user_update.new_password:
        new_hash = hash_password(user_update.new_password)

    if not new_username and not new_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Keine Änderungen angegeben",
        )

    updated = await update_user(
        user_id=current_user["id"],
        new_username=new_username,
        new_password_hash=new_hash,
    )

    effective_username = updated["username"]
    token = create_access_token(data={"sub": effective_username})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        max_age=settings.access_token_expire_minutes * 60,
        samesite="lax",
        secure=False,
        path="/",
    )

    is_admin = bool(updated.get("is_admin")) or (updated["username"] == settings.default_admin_user)
    return UserResponse(
        id=updated["id"],
        username=updated["username"],
        is_admin=is_admin,
        created_at=updated["created_at"],
    )
