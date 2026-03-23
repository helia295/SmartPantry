from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    display_name: str
    password: str


class UserRead(UserBase):
    id: int
    display_name: str
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    sub: Optional[str] = None


class UserTimezoneUpdate(BaseModel):
    timezone: str


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
