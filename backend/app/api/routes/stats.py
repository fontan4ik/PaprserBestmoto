from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...models import User
from ...schemas.stats import OverviewStats, UserStatsResponse
from ...services.stats_service import StatsService
from ..deps import get_current_admin

router = APIRouter()


@router.get("/overview", response_model=OverviewStats)
async def overview(
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = StatsService(db)
    return await service.overview()


@router.get("/users", response_model=list[UserStatsResponse])
async def users_stats(
    days: int = 14,
    _: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    service = StatsService(db)
    return await service.user_stats(days=days)

