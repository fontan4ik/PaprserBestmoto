from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ParsingTask, TaskLog
from ..models.enums import TaskStatus, TaskType


class LogService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_logs(
        self,
        limit: int,
        offset: int,
        user_id: int | None = None,
        task_type: TaskType | None = None,
        status: TaskStatus | None = None,
        level: str | None = None,
    ) -> tuple[int, Sequence[tuple[TaskLog, ParsingTask]]]:
        base_stmt = select(TaskLog, ParsingTask).join(
            ParsingTask, TaskLog.task_id == ParsingTask.id
        )
        if user_id:
            base_stmt = base_stmt.where(ParsingTask.user_id == user_id)
        if task_type:
            base_stmt = base_stmt.where(ParsingTask.task_type == task_type)
        if status:
            base_stmt = base_stmt.where(ParsingTask.status == status)
        if level:
            base_stmt = base_stmt.where(TaskLog.level == level.upper())

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await self.db.scalar(total_stmt)

        stmt = base_stmt.order_by(TaskLog.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return total or 0, result.all()

