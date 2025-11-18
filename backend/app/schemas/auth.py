from datetime import datetime

from pydantic import BaseModel

from ..models.enums import UserRole


class AuthValidateRequest(BaseModel):
    init_data: str


class AuthValidateResponse(BaseModel):
    telegram_id: int
    username: str | None
    first_name: str | None
    role: UserRole
    is_active: bool
    auth_date: datetime

