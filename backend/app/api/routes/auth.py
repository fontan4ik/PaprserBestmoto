from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...schemas.auth import AuthValidateRequest, AuthValidateResponse
from ...services.user_service import UserService
from ...utils.telegram import validate_init_data

router = APIRouter()


@router.post("/validate", response_model=AuthValidateResponse)
async def validate_auth(
    payload: AuthValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthValidateResponse:
    data = validate_init_data(payload.init_data)
    telegram_user = data.get("user") or {}
    service = UserService(db)
    user = await service.get_or_create_from_telegram(telegram_user)
    return AuthValidateResponse(
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        role=user.role,
        is_active=user.is_active,
        auth_date=user.auth_date,
    )

