import uuid
from typing import Any

from ..models.enums import TaskType
from .celery_app import celery_app


async def enqueue_task(
    task_id: uuid.UUID, task_type: TaskType, payload: dict | None, priority: int = 0
) -> None:
    celery_app.send_task(
        "app.workers.tasks.process_task",
        kwargs={
            "task_id": str(task_id),
            "task_type": task_type.value if hasattr(task_type, "value") else task_type,
            "payload": payload or {},
        },
        priority=max(min(priority, 9), 0),
    )

