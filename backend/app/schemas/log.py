from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from .pagination import PaginatedResponse


class TaskLogResponse(BaseModel):
    id: int
    task_id: UUID
    user_id: int | None
    message: str
    level: str
    created_at: datetime
    task_type: str | None = None
    task_status: str | None = None

    class Config:
        from_attributes = True


class TaskLogListResponse(PaginatedResponse):
    items: list[TaskLogResponse]

