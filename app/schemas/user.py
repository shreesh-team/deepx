from datetime import datetime

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    created_at: str

    @classmethod
    def from_orm(cls, user) -> "UserResponse":
        return cls(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at.strftime("%Y-%m-%d") if isinstance(user.created_at, datetime) else str(user.created_at)[:10],
        )
