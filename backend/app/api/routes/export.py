from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...clients.redis_client import get_redis_client
from ...db.session import get_db
from ...models import ExportHistory, User
from ...models.enums import TaskType
from ...schemas.export import ExportHistoryList, ExportHistoryResponse, GoogleExportRequest
from ...schemas.task import TaskCreateRequest, TaskResponse
from ...services.export_service import ExportService
from ...services.task_service import TaskService
from ..deps import get_current_admin, get_current_user, pagination_params

router = APIRouter()


@router.post("/google-sheets", response_model=ExportHistoryResponse)
async def export_google_sheets(
    payload: GoogleExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ExportService(db)
    history = await service.export_task(current_user, payload)
    return history


@router.get("/history", response_model=ExportHistoryList)
async def export_history(
    params=Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ExportHistory)
        .where(ExportHistory.user_id == current_user.telegram_id)
        .order_by(ExportHistory.created_at.desc())
        .offset(params.offset)
        .limit(params.limit)
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    total_stmt = select(func.count()).where(ExportHistory.user_id == current_user.telegram_id)
    total = await db.scalar(total_stmt)
    return ExportHistoryList(total=total or 0, limit=params.limit, offset=params.offset, items=items)


@router.post("/admin/full-backup", response_model=TaskResponse)
async def export_full_backup(
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = TaskService(db, get_redis_client())
    task = await service.create_task(
        admin,
        TaskCreateRequest(
            task_type=TaskType.FULL_BACKUP,
            payload={},
            priority=20,
        ),
    )
    return task

