"""Authentication and current-user endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.auth.models import User
from backend.auth.schemas import AuthResponse, AuthUserResponse, LoginRequest, SignupRequest, UserMeResponse
from backend.auth.utils import create_access_token, get_current_user, hash_password, verify_password
from backend.database import get_db

router = APIRouter(tags=["auth"])


@router.post("/api/auth/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return AuthResponse(token=token, user=AuthUserResponse.model_validate(user))


@router.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    token = create_access_token(user.id)
    return AuthResponse(token=token, user=AuthUserResponse.model_validate(user))


@router.get("/api/users/me", response_model=UserMeResponse)
def get_me(user_id: int = Depends(get_current_user), db: Session = Depends(get_db)) -> UserMeResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserMeResponse.model_validate(user)
