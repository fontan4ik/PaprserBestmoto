from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings
from .base import Base

# Supabase requires SSL connections - add ssl=require to URL if not present
from urllib.parse import quote_plus
from ..core.logging import get_logger

logger = get_logger("db")

db_url = settings.database_url
if not db_url:
    raise ValueError("DATABASE_URL is not set")

# Fix URL encoding for password if needed
if "supabase.co" in db_url:
    try:
        parsed = urlparse(db_url)
        # Extract password from netloc (format: user:password@host)
        if "@" in parsed.netloc:
            auth, host = parsed.netloc.rsplit("@", 1)
            if ":" in auth:
                user, password = auth.split(":", 1)
                # URL-encode password to handle special characters
                encoded_password = quote_plus(password)
                parsed = parsed._replace(netloc=f"{user}:{encoded_password}@{host}")
                db_url = urlunparse(parsed)
        
        # Add SSL parameter if not present
        parsed = urlparse(db_url)  # Re-parse after password encoding
        if "ssl=" not in db_url.lower():
            query_params = parse_qs(parsed.query)
            query_params["ssl"] = ["require"]
            new_query = urlencode(query_params, doseq=True)
            db_url = urlunparse(
                (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
            )
    except Exception as e:
        logger.warning("Failed to normalize database URL: %s. Using original URL.", e)

# Log connection info (without password) for debugging
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

