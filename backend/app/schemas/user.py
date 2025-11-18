from datetime import datetime

from pydantic import BaseModel

from ..models.enums import UserRole
from .pagination import PaginatedResponse


class UserBase(BaseModel):
    telegram_id: int
    username: str | None = None
    first_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime
    last_seen_at: datetime | None = None

    class Config:
        from_attributes = True


class UserListResponse(PaginatedResponse):
    items: list[UserBase]


class UserUpdateRequest(BaseModel):
    role: UserRole | None = None
    is_active: bool | None = None


class UserDeleteResponse(BaseModel):
    telegram_id: int
    deleted_tasks: int
    deleted_files: int

