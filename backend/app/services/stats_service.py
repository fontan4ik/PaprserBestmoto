from datetime import datetime, timedelta
from typing import List

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis_client import get_redis_client
from ..models import ExportHistory, ParsingTask, UploadedFile, User
from ..models.enums import TaskStatus
from ..schemas.stats import OverviewStats, UserStatsResponse


class StatsService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.redis = get_redis_client()

    async def overview(self) -> OverviewStats:
        cached = await self.redis.get("stats:overview")
        if cached:
            return OverviewStats.model_validate_json(cached)

        now = datetime.utcnow()
        last_30 = now - timedelta(days=30)

        active_users = await self.db.scalar(
            select(func.count()).select_from(User).where(User.is_active.is_(True))
        )
        completed_tasks = await self.db.scalar(
            select(func.count())
            .select_from(ParsingTask)
            .where(
                ParsingTask.status == TaskStatus.COMPLETED,
                ParsingTask.completed_at >= last_30,
            )
        )
        total_tasks = await self.db.scalar(select(func.count()).select_from(ParsingTask))
        durations = await self.db.execute(
            select(
                func.avg(
                    func.extract("epoch", ParsingTask.completed_at)
                    - func.extract("epoch", ParsingTask.started_at)
                )
            ).where(ParsingTask.status == TaskStatus.COMPLETED)
        )
        avg_duration = durations.scalar() or 0
        total_storage = await self.db.scalar(
            select(func.sum(UploadedFile.file_size)).select_from(UploadedFile)
        )

        overview = OverviewStats(
            active_users=active_users or 0,
            total_tasks=total_tasks or 0,
            completed_tasks=completed_tasks or 0,
            avg_duration_seconds=float(avg_duration),
            storage_usage_mb=((total_storage or 0) / (1024 * 1024)),
        )

        await self.redis.set("stats:overview", overview.model_dump_json(), ex=300)
        return overview

    async def user_stats(self, days: int = 14) -> List[UserStatsResponse]:
        cutoff = datetime.utcnow() - timedelta(days=days)

        new_users_stmt = (
            select(
                func.date_trunc("day", User.created_at).label("day"),
                func.count().label("count"),
            )
            .where(User.created_at >= cutoff)
            .group_by(func.date_trunc("day", User.created_at))
        )

        active_users_stmt = (
            select(
                func.date_trunc("day", User.last_seen_at).label("day"),
                func.count().label("count"),
            )
            .where(User.last_seen_at.is_not(None), User.last_seen_at >= cutoff)
            .group_by(func.date_trunc("day", User.last_seen_at))
        )

        new_users_result = await self.db.execute(new_users_stmt)
        new_users = {
            row.day.replace(tzinfo=None) if hasattr(row.day, "tzinfo") else row.day: row.count
            for row in new_users_result
        }

        active_users_result = await self.db.execute(active_users_stmt)
        active_users = {
            row.day.replace(tzinfo=None) if hasattr(row.day, "tzinfo") else row.day: row.count
            for row in active_users_result
        }

        stats: List[UserStatsResponse] = []
        for delta in range(days, -1, -1):
            day = datetime.utcnow() - timedelta(days=delta)
            key = day.replace(hour=0, minute=0, second=0, microsecond=0)
            stats.append(
                UserStatsResponse(
                    date=key,
                    new_users=int(new_users.get(key, 0)),
                    active_users=int(active_users.get(key, 0)),
                )
            )

        return stats

