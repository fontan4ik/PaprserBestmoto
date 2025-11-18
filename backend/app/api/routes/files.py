import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models import UploadedFile, User
from ...schemas.file import FileListResponse, FileResponse
from ...services.storage_service import StorageService
from ..deps import get_current_user, pagination_params

router = APIRouter()


@router.post("/upload", response_model=FileResponse)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadedFile:
    service = StorageService(db)
    entry = await service.save_file(current_user, file)
    return entry


@router.get("", response_model=FileListResponse)
async def list_files(
    params=Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileListResponse:
    stmt = (
        select(UploadedFile)
        .where(UploadedFile.user_id == current_user.telegram_id)
        .order_by(UploadedFile.upload_date.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    total_stmt = (
        select(func.count())
        .select_from(UploadedFile)
        .where(UploadedFile.user_id == current_user.telegram_id)
    )
    total = await db.scalar(total_stmt)
    return FileListResponse(total=total or 0, limit=params.limit, offset=params.offset, items=items)


@router.get("/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.get(UploadedFile, file_id)
    if not file or file.user_id != current_user.telegram_id:
        raise HTTPException(status_code=404, detail="Файл не найден.")
    service = StorageService(db)
    return {"url": service.generate_signed_url(file)}


@router.delete("/{file_id}")
async def delete_file(
    file_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    file = await db.get(UploadedFile, file_id)
    if not file or file.user_id != current_user.telegram_id:
        raise HTTPException(status_code=404, detail="Файл не найден.")
    service = StorageService(db)
    await service.delete_file(file)
    return {"status": "deleted"}

