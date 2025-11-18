from fastapi import APIRouter, Depends

from ...models import User
from ...schemas.user import UserBase
from ..deps import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserBase)
async def get_me(current_user: User = Depends(get_current_user)) -> User:
    return current_user

