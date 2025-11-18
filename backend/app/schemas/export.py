import uuid
from datetime import datetime

from pydantic import BaseModel, HttpUrl

from .pagination import PaginatedResponse


class GoogleExportRequest(BaseModel):
    task_id: uuid.UUID
    sheet_url: HttpUrl | None = None
    sheet_id: str | None = None
    template_name: str | None = None


class ExportHistoryResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID | None
    sheet_url: str
    sheet_tab_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class ExportHistoryList(PaginatedResponse):
    items: list[ExportHistoryResponse]

