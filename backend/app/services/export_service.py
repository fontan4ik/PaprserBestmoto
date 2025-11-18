import re
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import ExportHistory, ParsingTask, User
from ..models.enums import TaskStatus, UserRole
from ..schemas.export import GoogleExportRequest
from .google_service import GoogleSheetsService

SHEET_REGEX = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def extract_sheet_id(url_or_id: str) -> str:
    match = SHEET_REGEX.search(url_or_id)
    if match:
        return match.group(1)
    return url_or_id


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.google = GoogleSheetsService()

    async def export_task(
        self, user: User, payload: GoogleExportRequest
    ) -> ExportHistory:
        task: ParsingTask | None = await self.db.get(ParsingTask, payload.task_id)
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена.")
        if user.role != UserRole.ADMIN and task.user_id != user.telegram_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
        if task.status != TaskStatus.COMPLETED and user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Экспорт разрешён только после завершения задачи.",
            )

        sheet_id = None
        if payload.sheet_id:
            sheet_id = payload.sheet_id
        elif payload.sheet_url:
            sheet_id = extract_sheet_id(payload.sheet_url)

        if not sheet_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Не удалось определить ID таблицы Google Sheets.",
            )

        rows = self._build_rows(task)
        tab_name = payload.template_name or datetime.utcnow().strftime(
            "%Y-%m-%d_%H-%M"
        )

        self.google.export_task(task, sheet_id, tab_name, rows)

        history = ExportHistory(
            user_id=user.telegram_id,
            task_id=task.id,
            sheet_id=sheet_id,
            sheet_url=payload.sheet_url or f"https://docs.google.com/spreadsheets/d/{sheet_id}",
            sheet_tab_name=tab_name,
            status="completed",
            created_at=datetime.now(tz=timezone.utc),
        )
        self.db.add(history)
        await self.db.commit()
        await self.db.refresh(history)
        return history

    def _build_rows(self, task: ParsingTask) -> list[list[str]]:
        result = task.result_data or {}
        headers = result.get("headers")
        rows = result.get("rows")
        if headers and rows:
            return [headers] + rows
        if isinstance(result, list):
            keys = sorted({k for row in result for k in row.keys()})
            formatted_rows = [
                [row.get(key, "") for key in keys] for row in result
            ]
            return [keys] + formatted_rows
        return [["message"], ["Результаты отсутствуют"]]

