from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from ..models import ParsingTask, UploadedFile, User
from ..models.enums import UserRole
from ..schemas.user import UserDeleteResponse, UserUpdateRequest
from ..services.storage_service import StorageService


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create_from_telegram(self, telegram_user: dict) -> User:
        telegram_id = telegram_user["id"]
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        auth_date = datetime.now(tz=timezone.utc)

        if user:
            user.username = telegram_user.get("username")
            user.first_name = telegram_user.get("first_name")
            user.last_seen_at = auth_date
            user.auth_date = auth_date
        else:
            user = User(
                telegram_id=telegram_id,
                username=telegram_user.get("username"),
                first_name=telegram_user.get("first_name"),
                role=UserRole.USER,
                is_active=True,
                last_seen_at=auth_date,
                auth_date=auth_date,
            )
            self.db.add(user)

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def list_users(
        self,
        limit: int,
        offset: int,
        role: UserRole | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[int, Sequence[User]]:
        filters = []

        if role:
            filters.append(User.role == role)
        if is_active is not None:
            filters.append(User.is_active == is_active)
        if search:
            filters.append(
                (User.username.ilike(f"%{search}%"))
                | (cast(User.telegram_id, String).ilike(f"%{search}%"))
            )

        base_stmt = select(User)
        if filters:
            base_stmt = base_stmt.where(*filters)

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total = await self.db.scalar(total_stmt)

        stmt = base_stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return total or 0, result.scalars().all()

    async def update_user(self, telegram_id: int, payload: UserUpdateRequest) -> User:
        user = await self.db.get(User, telegram_id)
        if not user:
            raise ValueError("Пользователь не найден")

        if payload.role:
            user.role = payload.role
        if payload.is_active is not None:
            user.is_active = payload.is_active

        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete_user(self, telegram_id: int) -> UserDeleteResponse | None:
        user = await self.db.get(User, telegram_id)
        if not user:
            return None

        tasks_count = await self.db.scalar(
            select(func.count()).select_from(ParsingTask).where(ParsingTask.user_id == telegram_id)
        )

        files_stmt = select(UploadedFile).where(UploadedFile.user_id == telegram_id)
        files = (await self.db.execute(files_stmt)).scalars().all()
        try:
            storage = StorageService(self.db) if files else None
        except RuntimeError:
            storage = None
        deleted_files = 0
        if storage:
            for file in files:
                await storage.delete_file(file)
                deleted_files += 1

        await self.db.delete(user)
        await self.db.commit()

        return UserDeleteResponse(
            telegram_id=telegram_id,
            deleted_tasks=tasks_count or 0,
            deleted_files=deleted_files,
        )

