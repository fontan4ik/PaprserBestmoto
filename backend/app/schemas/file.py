import uuid
from datetime import datetime

from pydantic import BaseModel

from .pagination import PaginatedResponse


class FileResponse(BaseModel):
    id: uuid.UUID
    filename: str
    file_size: int
    upload_date: datetime

    class Config:
        from_attributes = True


class FileListResponse(PaginatedResponse):
    items: list[FileResponse]

