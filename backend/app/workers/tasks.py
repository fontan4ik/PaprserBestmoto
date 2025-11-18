import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone

from celery import states
from celery.schedules import crontab
from sqlalchemy import select

from ..clients.redis_client import get_redis_client
from ..core.logging import get_logger
from ..db.session import AsyncSessionLocal
from ..models import ArchivedTask, ParsingTask, TaskLog, UploadedFile
from ..models.enums import TaskStatus, TaskType
from ..services.export_service import extract_sheet_id
from ..services.google_service import GoogleSheetsService
from ..services.legacy_bridge import LegacyBridge
from ..services.storage_service import StorageService
from .celery_app import celery_app
@celery_app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    sender.add_periodic_task(
        crontab(hour=3, minute=0), cleanup_old_files.s(), name="cleanup-supabase-files"
    )
    sender.add_periodic_task(
        crontab(hour=4, minute=0), archive_old_tasks.s(), name="archive-old-tasks"
    )


logger = get_logger("celery_tasks")
bridge = LegacyBridge()
google_service = GoogleSheetsService()


def _now():
    return datetime.now(tz=timezone.utc)


async def _update_task(task_id: uuid.UUID, **kwargs) -> None:
    async with AsyncSessionLocal() as session:
        task = await session.get(ParsingTask, task_id)
        if not task:
            return
        for key, value in kwargs.items():
            setattr(task, key, value)
        await session.commit()


async def _log_task(task_id: uuid.UUID, message: str, level: str = "INFO") -> None:
    async with AsyncSessionLocal() as session:
        log = TaskLog(task_id=task_id, user_id=None, message=message, level=level)
        session.add(log)
        await session.commit()


async def _publish_progress(task_id: uuid.UUID, status: TaskStatus, progress: int, payload: dict | None = None):
    redis = get_redis_client()
    message = {
        "task_id": str(task_id),
        "status": status.value if hasattr(status, "value") else status,
        "progress": progress,
        "payload": payload or {},
    }
    await redis.hset(
        f"task:{task_id}", mapping={"status": message["status"], "progress": progress}
    )
    await redis.publish("tasks:updates", json.dumps(message))


async def _execute(task_id: uuid.UUID, task_type: TaskType, payload: dict):
    await _update_task(
        task_id,
        status=TaskStatus.PROCESSING,
        started_at=_now(),
        progress_percentage=5,
    )
    await _publish_progress(task_id, TaskStatus.PROCESSING, 5)
    await _log_task(task_id, f"Задача {task_type.value} запущена.")

    result_data = {}
    try:
        if task_type == TaskType.PARSE_MARKETPLACE:
            query = payload.get("query")
            marketplaces = payload.get("marketplaces")
            scraped = bridge.scrape_marketplace(query, marketplaces)
            result_data = {"marketplaces": scraped}
        elif task_type == TaskType.IMPORT_COMMERCEML:
            file_path = payload["file_path"]
            result_data = {"products": bridge.parse_commerceml(file_path)}
        elif task_type == TaskType.MATCH_PRODUCTS:
            products_1c = payload["products_1c"]
            scraped = payload["scraped_products"]
            matches = bridge.match_products(products_1c, scraped)
            result_data = {"matches": matches}
        elif task_type == TaskType.EXPORT_GOOGLE:
            sheet_id = extract_sheet_id(payload.get("sheet_url") or payload.get("sheet_id"))
            rows = payload.get("rows", [])
            google_service.export_task(
                task=await _get_task(task_id),
                sheet_id=sheet_id,
                sheet_tab=payload.get("sheet_tab"),
                rows=rows,
            )
            result_data = {"sheet_id": sheet_id}
        else:
            raise ValueError(f"Неизвестный тип задачи: {task_type}")

        await _update_task(
            task_id,
            status=TaskStatus.COMPLETED,
            progress_percentage=100,
            completed_at=_now(),
            result_data=result_data,
            error_message=None,
        )
        await _publish_progress(task_id, TaskStatus.COMPLETED, 100, {"result": result_data})
        await _log_task(task_id, "Задача успешно завершена.")
    except Exception as exc:
        logger.exception("Task %s failed: %s", task_id, exc)
        await _update_task(
            task_id,
            status=TaskStatus.FAILED,
            progress_percentage=100,
            completed_at=_now(),
            error_message=str(exc),
        )
        await _publish_progress(task_id, TaskStatus.FAILED, 100, {"error": str(exc)})
        await _log_task(task_id, f"Ошибка выполнения: {exc}", level="ERROR")
        raise


async def _get_task(task_id: uuid.UUID) -> ParsingTask:
    async with AsyncSessionLocal() as session:
        task = await session.get(ParsingTask, task_id)
        if not task:
            raise ValueError("Задача не найдена.")
        return task


async def _cleanup_old_files() -> None:
    cutoff = _now() - timedelta(days=30)
    async with AsyncSessionLocal() as session:
        stmt = select(UploadedFile).where(UploadedFile.upload_date < cutoff)
        files = (await session.execute(stmt)).scalars().all()
        if not files:
            return
        storage = StorageService(session)
        for file in files:
            await storage.delete_file(file)


async def _archive_old_tasks() -> None:
    cutoff = _now() - timedelta(days=90)
    async with AsyncSessionLocal() as session:
        stmt = select(ParsingTask).where(ParsingTask.completed_at < cutoff)
        tasks = (await session.execute(stmt)).scalars().all()
        if not tasks:
            return
        for task in tasks:
            archived = ArchivedTask(
                id=task.id,
                user_id=task.user_id,
                task_type=task.task_type,
                status=task.status,
                priority=task.priority,
                result_data=task.result_data,
                error_message=task.error_message,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
            )
            session.add(archived)
            await session.delete(task)
        await session.commit()


@celery_app.task(name="app.workers.tasks.cleanup_old_files")
def cleanup_old_files():
    asyncio.run(_cleanup_old_files())


@celery_app.task(name="app.workers.tasks.archive_old_tasks")
def archive_old_tasks():
    asyncio.run(_archive_old_tasks())


@celery_app.task(
    name="app.workers.tasks.process_task",
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)
def process_task(self, task_id: str, task_type: str, payload: dict):
    self.update_state(state=states.STARTED, meta={"task_id": task_id})
    asyncio.run(_execute(uuid.UUID(task_id), TaskType(task_type), payload))

