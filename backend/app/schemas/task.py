import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from ..models.enums import TaskStatus, TaskType
from .pagination import PaginatedResponse


class TaskCreateRequest(BaseModel):
    task_type: TaskType
    payload: dict = Field(default_factory=dict)
    priority: int | None = None


class ParseTaskPayload(BaseModel):
    query: str
    marketplaces: list[str] | None = None
    max_products: int = Field(50, ge=1, le=1000)


class FileImportPayload(BaseModel):
    file_id: str
    file_type: str


class MatchTaskPayload(BaseModel):
    products_1c_file_id: str
    scraped_source_task_id: str
    threshold: float | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    task_type: TaskType
    status: TaskStatus
    progress_percentage: int
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_data: dict | None = None
    error_message: str | None = None
    priority: int

    class Config:
        from_attributes = True


class TaskListResponse(PaginatedResponse):
    items: list[TaskResponse]


class TaskProgressResponse(BaseModel):
    status: TaskStatus
    progress: int
    payload: dict | None = None

