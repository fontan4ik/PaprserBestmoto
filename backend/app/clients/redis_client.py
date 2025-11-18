from typing import Optional

from redis.asyncio import Redis

from ..core.config import settings

_redis: Optional[Redis] = None


def get_redis_client() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis

