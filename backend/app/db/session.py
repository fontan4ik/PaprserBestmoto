from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings
from .base import Base

# Supabase requires SSL connections - add ssl=require to URL if not present
db_url = settings.database_url
if "supabase.co" in db_url and "ssl=" not in db_url:
    parsed = urlparse(db_url)
    query_params = parse_qs(parsed.query)
    query_params["ssl"] = ["require"]
    new_query = urlencode(query_params, doseq=True)
    db_url = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )

# Log connection info (without password) for debugging
from ..core.logging import get_logger
logger = get_logger("db")
if db_url:
    safe_url = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info("Connecting to database: %s", safe_url)

engine = create_async_engine(
    db_url,
    echo=not settings.is_production,
    pool_size=10,
    max_overflow=20,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

