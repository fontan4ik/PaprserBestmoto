import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...clients.redis_client import get_redis_client
from ...db.session import get_db
from ...models import ParsingTask, User
from ...models.enums import TaskStatus, TaskType
from ...schemas.task import (
    MatchTaskPayload,
    ParseTaskPayload,
    TaskCreateRequest,
    TaskListResponse,
    TaskProgressResponse,
    TaskResponse,
)
from ...services.task_service import TaskService
from ..deps import get_current_admin, get_current_user, pagination_params

router = APIRouter()


def _service(db: AsyncSession) -> TaskService:
    return TaskService(db, get_redis_client())


@router.post("/parse", response_model=TaskResponse)
async def create_parse_task(
    payload: ParseTaskPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParsingTask:
    service = _service(db)
    task = await service.create_task(
        current_user,
        TaskCreateRequest(
            task_type=TaskType.PARSE_MARKETPLACE,
            payload=payload.model_dump(),
        ),
    )
    return task


@router.get("", response_model=TaskListResponse)
async def list_tasks(
    params=Depends(pagination_params),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TaskListResponse:
    service = _service(db)
    total, items = await service.list_tasks(current_user, params.limit, params.offset)
    return TaskListResponse(total=total, limit=params.limit, offset=params.offset, items=items)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParsingTask:
    service = _service(db)
    return await service.get_task(task_id, current_user)


@router.get("/{task_id}/progress", response_model=TaskProgressResponse)
async def get_task_progress(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = _service(db)
    await service.get_task(task_id, current_user)
    redis = get_redis_client()
    data = await redis.hgetall(f"task:{task_id}")
    if not data:
        raise HTTPException(status_code=404, detail="Прогресс не найден.")
    status_value = data.get("status", TaskStatus.PENDING.value)
    return TaskProgressResponse(
        status=TaskStatus(status_value),
        progress=int(data.get("progress", 0)),
    )


@router.delete("/{task_id}", response_model=TaskResponse)
async def cancel_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ParsingTask:
    service = _service(db)
    task = await service.get_task(task_id, current_user)
    return await service.cancel_task(task)


@router.post("/{task_id}/restart", response_model=TaskResponse)
async def restart_task(
    task_id: uuid.UUID,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> ParsingTask:
    service = _service(db)
    task = await service.get_task(task_id, admin)
    return await service.restart_task(task)



