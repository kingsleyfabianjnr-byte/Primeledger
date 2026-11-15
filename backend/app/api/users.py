"""User management API — admin CRUD, invite, password reset, profile."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import get_current_user, hash_password
from app.core.config import settings
from app.models.user import User, UserRole
from app.schemas.auth import UserRead, UserUpdate
from app.services.email import generate_token, token_expiry, send_invite_email, send_password_reset_email

router = APIRouter(prefix="/api/users", tags=["users"])


# ── Helper ────────────────────────────────────────────────────────────────────

def _require_admin(current_user: User):
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin access required")


# ── List all users (admin only) ───────────────────────────────────────────────

@router.get("", response_model=list[UserRead])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


# ── Get single user (admin or self) ──────────────────────────────────────────

@router.get("/{user_id}", response_model=UserRead)
async def get_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.id != user_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ── Update user role / active status (admin only) ────────────────────────────

@router.patch("/{user_id}", response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    await db.commit()
    await db.refresh(user)
    return user


# ── Delete user (admin only) ──────────────────────────────────────────────────

@router.delete("/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()


# ── Invite new user (admin only) ──────────────────────────────────────────────

class InvitePayload(BaseModel):
    email: EmailStr
    full_name: str
    role: UserRole = UserRole.PREPARER


@router.post("/invite", response_model=UserRead, status_code=201)
async def invite_user(
    payload: InvitePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    # Check email not already taken
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    token = generate_token()
    expiry = token_expiry(hours=48)

    new_user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(token),  # temporary — overwritten on setup
        role=payload.role,
        is_active=False,  # inactive until they set up their account
        pending_setup=True,
        invite_token=token,
        invite_token_expiry=expiry,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    send_invite_email(
        to_email=payload.email,
        inviter_name=current_user.full_name,
        token=token,
        app_url=settings.FRONTEND_URL,
    )

    return new_user


# ── Setup account (from invite link) ─────────────────────────────────────────

class SetupAccountPayload(BaseModel):
    token: str
    password: str


@router.post("/setup-account")
async def setup_account(
    payload: SetupAccountPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.invite_token == payload.token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired invite link")
    if user.invite_token_expiry and user.invite_token_expiry < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invite link has expired — ask admin to re-invite you")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(payload.password)
    user.is_active = True
    user.pending_setup = False
    user.invite_token = None
    user.invite_token_expiry = None
    await db.commit()

    return {"message": "Account set up successfully. You can now log in."}


# ── Forgot password ───────────────────────────────────────────────────────────

class ForgotPasswordPayload(BaseModel):
    email: EmailStr


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Always return success (don't reveal if email exists)
    if user and user.is_active:
        token = generate_token()
        user.reset_token = token
        user.reset_token_expiry = token_expiry(hours=1)
        await db.commit()
        send_password_reset_email(
            to_email=user.email,
            token=token,
            app_url=settings.FRONTEND_URL,
        )

    return {"message": "If that email exists, a reset link has been sent."}


# ── Reset password (from email link) ─────────────────────────────────────────

class ResetPasswordPayload(BaseModel):
    token: str
    new_password: str


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordPayload,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.reset_token == payload.token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link")
    if user.reset_token_expiry and user.reset_token_expiry < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset link has expired — request a new one")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user.hashed_password = hash_password(payload.new_password)
    user.reset_token = None
    user.reset_token_expiry = None
    await db.commit()

    return {"message": "Password reset successfully. You can now log in."}


# ── Update own profile ────────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None


@router.patch("/me/profile", response_model=UserRead)
async def update_profile(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.full_name:
        current_user.full_name = payload.full_name

    if payload.new_password:
        if not payload.current_password:
            raise HTTPException(status_code=400, detail="Current password is required")
        import bcrypt as _bcrypt
        if not _bcrypt.checkpw(payload.current_password.encode(), current_user.hashed_password.encode()):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        if len(payload.new_password) < 8:
            raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
        current_user.hashed_password = hash_password(payload.new_password)

    await db.commit()
    await db.refresh(current_user)
    return current_user
