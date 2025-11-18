import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models import ParsingTask, User
from ..models.enums import TaskStatus, TaskType, UserRole
from ..schemas.task import TaskCreateRequest
from ..workers.queue import enqueue_task


class TaskService:
    def __init__(self, db: AsyncSession, redis: Redis):
        self.db = db
        self.redis = redis

    async def _get_concurrent_tasks(self, user: User) -> int:
        stmt = select(func.count()).where(
            ParsingTask.user_id == user.telegram_id,
            ParsingTask.status.in_([TaskStatus.PENDING, TaskStatus.PROCESSING]),
        )
        return await self.db.scalar(stmt) or 0

    async def _enforce_task_limit(self, user: User) -> None:
        limit = (
            settings.rate_limit.admin_concurrent_tasks
            if user.role == UserRole.ADMIN
            else settings.rate_limit.user_concurrent_tasks
        )
        if limit <= 0:
            return
        current = await self._get_concurrent_tasks(user)
        if current >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит одновременных задач.",
            )

    async def create_task(self, user: User, payload: TaskCreateRequest) -> ParsingTask:
        await self._enforce_task_limit(user)

        priority = payload.priority
        if priority is None:
            priority = 10 if user.role == UserRole.ADMIN else 0

        task = ParsingTask(
            user_id=user.telegram_id,
            task_type=payload.task_type,
            status=TaskStatus.PENDING,
            progress_percentage=0,
            priority=priority,
            input_payload=payload.payload,
            result_data=None,
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        await self.redis.hset(
            f"task_meta:{task.id}",
            mapping={"user_id": user.telegram_id, "task_type": task.task_type.value},
        )

        await enqueue_task(
            task_id=task.id,
            task_type=task.task_type,
            payload=payload.payload,
            priority=priority,
        )
        return task

    async def list_tasks(
        self, user: User | None, limit: int, offset: int, all_users: bool = False
    ) -> tuple[int, list[ParsingTask]]:
        filters = []
        if not all_users and user:
            filters.append(ParsingTask.user_id == user.telegram_id)

        base_stmt = select(ParsingTask)
        if filters:
            base_stmt = base_stmt.where(*filters)

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await self.db.scalar(total_stmt)
        stmt = (
            base_stmt.order_by(
                ParsingTask.priority.desc(), ParsingTask.created_at.desc()
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return total or 0, result.scalars().all()

    async def get_task(self, task_id: uuid.UUID, user: User | None = None) -> ParsingTask:
        task = await self.db.get(ParsingTask, task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        if user and task.user_id != user.telegram_id and user.role != UserRole.ADMIN:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        return task

    async def cancel_task(self, task: ParsingTask) -> ParsingTask:
        if task.status not in (TaskStatus.PENDING, TaskStatus.PROCESSING):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя отменить выполненную задачу.")
        task.status = TaskStatus.CANCELLED
        task.completed_at = datetime.now(tz=timezone.utc)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def restart_task(self, task: ParsingTask) -> ParsingTask:
        if task.status not in (TaskStatus.FAILED, TaskStatus.CANCELLED):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Перезапуск разрешён только для проваленных задач.")
        task.status = TaskStatus.PENDING
        task.progress_percentage = 0
        task.error_message = None
        task.result_data = None
        task.started_at = None
        task.completed_at = None
        await self.db.commit()
        await self.db.refresh(task)
        await enqueue_task(
            task.id, task.task_type, task.input_payload or {}, priority=task.priority
        )
        return task

