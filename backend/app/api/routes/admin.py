import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...clients.redis_client import get_redis_client
from ...db.session import get_db
from ...models import User
from ...models.enums import TaskStatus, TaskType, UserRole
from ...schemas.log import TaskLogListResponse, TaskLogResponse
from ...schemas.task import TaskListResponse, TaskResponse
from ...schemas.user import UserBase, UserDeleteResponse, UserListResponse, UserUpdateRequest
from ...services.log_service import LogService
from ...services.task_service import TaskService
from ...services.user_service import UserService
from ..deps import get_current_admin, pagination_params

router = APIRouter()


@router.get("/users", response_model=UserListResponse)
async def admin_list_users(
    params=Depends(pagination_params),
    role: UserRole | None = None,
    is_active: bool | None = None,
    search: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> UserListResponse:
    service = UserService(db)
    total, items = await service.list_users(params.limit, params.offset, role, is_active, search)
    return UserListResponse(total=total, limit=params.limit, offset=params.offset, items=items)


@router.put("/users/{telegram_id}", response_model=UserBase)
async def admin_update_user(
    telegram_id: int,
    payload: UserUpdateRequest,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    try:
        user = await service.update_user(telegram_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return user


@router.delete("/users/{telegram_id}", response_model=UserDeleteResponse)
async def admin_delete_user(
    telegram_id: int,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = UserService(db)
    deleted = await service.delete_user(telegram_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Пользователь не найден.")
    return deleted


def _task_service(db: AsyncSession) -> TaskService:
    return TaskService(db, get_redis_client())


@router.get("/tasks", response_model=TaskListResponse)
async def admin_tasks(
    params=Depends(pagination_params),
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = _task_service(db)
    total, items = await service.list_tasks(admin, params.limit, params.offset, all_users=True)
    return TaskListResponse(total=total, limit=params.limit, offset=params.offset, items=items)


@router.get("/logs", response_model=TaskLogListResponse)
async def admin_logs(
    params=Depends(pagination_params),
    user_id: int | None = None,
    task_type: TaskType | None = None,
    status: TaskStatus | None = None,
    level: str | None = None,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = LogService(db)
    total, rows = await service.list_logs(
        limit=params.limit,
        offset=params.offset,
        user_id=user_id,
        task_type=task_type,
        status=status,
        level=level,
    )

    items: list[TaskLogResponse] = []
    for log, task in rows:
        items.append(
            TaskLogResponse(
                id=log.id,
                task_id=log.task_id,
                user_id=log.user_id,
                message=log.message,
                level=log.level,
                created_at=log.created_at,
                task_type=task.task_type.value,
                task_status=task.status.value,
            )
        )

    return TaskLogListResponse(total=total, limit=params.limit, offset=params.offset, items=items)

