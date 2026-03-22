from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
)
from app.db import get_db
from app.models import User
from app.schemas import (
    Token,
    UserCreate,
    UserPasswordUpdate,
    UserProfileUpdate,
    UserRead,
    UserTimezoneUpdate,
)


router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(user_in: UserCreate, db: Session = Depends(get_db)) -> UserRead:
    existing = db.query(User).filter(User.email == user_in.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email already exists",
        )

    display_name = user_in.display_name.strip()
    if not display_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Display name is required",
        )

    user = User(
        email=user_in.email,
        display_name=display_name,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(user_in: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    user = db.query(User).filter(User.email == user_in.username).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(subject=str(user.id))
    return Token(access_token=access_token, token_type="bearer")


@router.post("/refresh", response_model=Token)
def refresh_access_token(current_user: User = Depends(get_current_user)) -> Token:
    access_token = create_access_token(subject=str(current_user.id))
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserRead)
def read_me(current_user: User = Depends(get_current_user)) -> UserRead:
    return current_user


def validate_timezone_or_raise(timezone_value: str) -> str:
    cleaned = timezone_value.strip()
    try:
        ZoneInfo(cleaned)
    except ZoneInfoNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid timezone",
        )
    return cleaned


@router.patch("/me", response_model=UserRead)
def update_profile(
    profile_in: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    if profile_in.display_name is not None:
        display_name = profile_in.display_name.strip()
        if not display_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name cannot be blank",
            )
        current_user.display_name = display_name

    if profile_in.email is not None:
        existing = (
            db.query(User)
            .filter(User.email == profile_in.email, User.id != current_user.id)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )
        current_user.email = profile_in.email

    if profile_in.timezone is not None:
        current_user.timezone = validate_timezone_or_raise(profile_in.timezone)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.patch("/me/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    password_in: UserPasswordUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    if not verify_password(password_in.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if len(password_in.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long",
        )

    current_user.hashed_password = get_password_hash(password_in.new_password)
    db.add(current_user)
    db.commit()


@router.patch("/me/timezone", response_model=UserRead)
def update_timezone(
    timezone_in: UserTimezoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UserRead:
    current_user.timezone = validate_timezone_or_raise(timezone_in.timezone)
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
