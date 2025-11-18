import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from urllib.parse import parse_qsl

from fastapi import HTTPException, status

from ..core.config import settings


class TelegramInitDataError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def parse_init_data(init_data: str) -> Dict[str, Any]:
    return dict(parse_qsl(init_data, strict_parsing=True))


def validate_init_data(init_data: str) -> Dict[str, Any]:
    data = parse_init_data(init_data)
    hash_value = data.pop("hash", None)
    if not hash_value:
        raise TelegramInitDataError("Отсутствует подпись Telegram.")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(settings.telegram_bot_token.encode()).digest()
    calculated_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(calculated_hash, hash_value):
        raise TelegramInitDataError("Невалидная подпись Telegram.")

    auth_date = data.get("auth_date")
    if auth_date:
        auth_dt = datetime.fromtimestamp(int(auth_date), tz=timezone.utc)
        if datetime.now(tz=timezone.utc) - auth_dt > timedelta(hours=24):
            raise TelegramInitDataError("Срок действия auth_date истёк.")

    user_payload = data.get("user")
    if user_payload:
        data["user"] = json.loads(user_payload)

    return data

