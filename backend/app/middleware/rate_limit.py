from datetime import datetime

from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from ..clients.redis_client import get_redis_client
from ..core.config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    exempt_paths = {"/", "/ping", "/healthz", "/health2", "/docs", "/openapi.json", "/api/auth/validate"}

    async def dispatch(self, request, call_next):
        path = request.url.path.rstrip("/") or "/"
        if path in self.exempt_paths or request.method == "OPTIONS":
            return await call_next(request)

        telegram_user = getattr(request.state, "telegram_user", None)
        if not telegram_user:
            return await call_next(request)

        user_id = telegram_user.get("id")
        if not user_id:
            return await call_next(request)

        redis = get_redis_client()
        role_key = f"user_role:{user_id}"
        role = await redis.get(role_key) or "USER"

        if role == "ADMIN" and settings.rate_limit.admin_limit == 0:
            return await call_next(request)

        limit = (
            settings.rate_limit.admin_limit
            if role == "ADMIN"
            else settings.rate_limit.user_limit
        )
        if limit <= 0:
            return await call_next(request)

        window = datetime.utcnow().strftime("%Y%m%d%H")
        key = f"rate:{user_id}:{window}"
        current = await redis.incr(key)
        if current == 1:
            await redis.expire(key, 3600)

        if current > limit:
            ttl = await redis.ttl(key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Превышен лимит запросов. Попробуйте позже.",
                headers={"Retry-After": str(max(ttl, 0))},
            )

        return await call_next(request)

