from fastapi import HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.telegram import TelegramInitDataError, validate_init_data


class TelegramInitDataMiddleware(BaseHTTPMiddleware):
    """Validates Telegram initData signature for every request."""

    header_name = "X-Telegram-Init-Data"
    exempt_paths = {
        "/",
        "/ping",
        "/health2",
        "/docs",
        "/openapi.json",
        "/metrics",
        "/api/auth/validate",
    }

    async def dispatch(self, request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path.rstrip("/")
        if not path:
            path = "/"

        if path in self.exempt_paths:
            return await call_next(request)

        init_data = request.headers.get(self.header_name) or request.query_params.get(
            "init_data"
        )
        if not init_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Отсутствует заголовок X-Telegram-Init-Data.",
            )

        try:
            request.state.telegram_data = validate_init_data(init_data)
            request.state.telegram_user = request.state.telegram_data.get("user")
        except TelegramInitDataError as exc:
            raise exc

        return await call_next(request)

