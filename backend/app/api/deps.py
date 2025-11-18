from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..clients.redis_client import get_redis_client
from ..db.session import get_db
from ..models import User
from ..models.enums import UserRole
from ..schemas.pagination import PaginationParams


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    telegram_user = getattr(request.state, "telegram_user", None)
    if not telegram_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)

    user = await db.get(User, telegram_user["id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не найден. Повторите авторизацию.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь заблокирован администратором.",
        )

    redis = get_redis_client()
    await redis.set(f"user_role:{user.telegram_id}", user.role.value, ex=3600)

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ разрешён только администраторам.",
        )
    return user


def pagination_params(limit: int = 20, offset: int = 0) -> PaginationParams:
    return PaginationParams(limit=limit, offset=offset)

