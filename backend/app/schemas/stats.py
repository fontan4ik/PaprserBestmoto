from datetime import datetime

from pydantic import BaseModel


class OverviewStats(BaseModel):
    active_users: int
    total_tasks: int
    completed_tasks: int
    avg_duration_seconds: float
    storage_usage_mb: float


class UserStatsResponse(BaseModel):
    date: datetime
    new_users: int
    active_users: int


class LogsFilter(BaseModel):
    user_id: int | None = None
    task_type: str | None = None
    status: str | None = None
    level: str | None = None

