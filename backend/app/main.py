from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from .api.router import api_router
from .core.config import settings
from .core.events import lifespan
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.telegram_init import TelegramInitDataMiddleware


def create_app() -> FastAPI:
    app = FastAPI(
        title="Parser Bestmoto API",
        version="1.0.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url="/redoc" if settings.environment != "production" else None,
        lifespan=lifespan,
        default_response_class=settings.default_response_class,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=500)

    app.add_middleware(TelegramInitDataMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.get("/")
    async def root():
        """Root endpoint"""
        return {"status": "ok", "service": "parser-bestmoto-api"}

    @app.get("/ping")
    async def ping():
        """Simple health check endpoint for Railway - no checks required"""
        return {"status": "ok"}

    @app.get("/healthz")
    async def health_check():
        """Health check endpoint that doesn't require database"""
        return {"status": "ok", "service": "parser-bestmoto-api"}

     @app.get("/health2")
    async def health2_check():
        """Health check endpoint v2"""
        return {"status": "ok", "service": "parser-bestmoto-api"}

    app.include_router(api_router, prefix="/api")

    return app


app = create_app()
