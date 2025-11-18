from contextlib import asynccontextmanager

from ..clients.redis_client import get_redis_client
from ..core.config import settings
from ..core.logging import get_logger, setup_logging
from ..models import User
from ..models.enums import UserRole
from ..db.session import AsyncSessionLocal, init_db

logger = get_logger("events")


async def ensure_initial_admin() -> None:
    if not settings.initial_admin_telegram_id:
        return

    admin_id = int(settings.initial_admin_telegram_id)
    async with AsyncSessionLocal() as session:
        admin = await session.get(User, admin_id)
        if admin:
            if admin.role != UserRole.ADMIN:
                admin.role = UserRole.ADMIN
                logger.info("Upgraded existing user %s to ADMIN", admin_id)
        else:
            admin = User(
                telegram_id=admin_id,
                username="initial_admin",
                first_name="Admin",
                role=UserRole.ADMIN,
                is_active=True,
            )
            session.add(admin)
            logger.info("Created initial admin user %s", admin_id)
        await session.commit()


@asynccontextmanager
async def lifespan(app):
    setup_logging(settings.log_level)
    redis = get_redis_client()
    await init_db()
    await ensure_initial_admin()

    logger.info("Application startup complete.")
    try:
        yield
    finally:
        await redis.close()
        logger.info("Application shutdown complete.")

