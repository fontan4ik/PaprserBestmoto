import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from supabase import Client, create_client

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import UploadedFile, User

ALLOWED_EXTENSIONS = {".xml", ".xlsx", ".mxl"}


def _create_supabase_client() -> Client:
    if not settings.supabase_project_url or not settings.supabase_service_key:
        raise RuntimeError("Supabase credentials are not configured.")
    return create_client(settings.supabase_project_url, settings.supabase_service_key)


def sanitize_filename(filename: str) -> str:
    filename = Path(filename).name
    filename = re.sub(r"[^A-Za-z0-9._-]", "_", filename)
    return filename[:120]


class StorageService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.client = _create_supabase_client()

    async def save_file(self, user: User, upload: UploadFile) -> UploadedFile:
        ext = Path(upload.filename or "").suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Разрешены только файлы xml, xlsx, mxl.",
            )

        content = await upload.read()
        size_mb = len(content) / (1024 * 1024)
        limit = (
            settings.max_file_size_admin_mb
            if user.role.name == "ADMIN"
            else settings.max_file_size_mb
        )
        if size_mb > limit:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Размер файла превышает {limit} МБ.",
            )

        remote_path = (
            f"{user.telegram_id}/{uuid.uuid4()}_{sanitize_filename(upload.filename)}"
        )
        self.client.storage.from_(settings.supabase_bucket).upload(
            remote_path,
            content,
            {"content-type": upload.content_type or "application/octet-stream"},
        )

        file_entry = UploadedFile(
            user_id=user.telegram_id,
            filename=upload.filename,
            file_path=remote_path,
            file_size=len(content),
        )
        self.db.add(file_entry)
        await self.db.commit()
        await self.db.refresh(file_entry)
        return file_entry

    def generate_signed_url(self, file: UploadedFile) -> str:
        response = self.client.storage.from_(settings.supabase_bucket).create_signed_url(
            file.file_path, 3600
        )
        return response.get("signedURL")

    async def delete_file(self, file: UploadedFile) -> None:
        self.client.storage.from_(settings.supabase_bucket).remove([file.file_path])
        await self.db.delete(file)
        await self.db.commit()

