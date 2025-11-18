import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ...clients.redis_client import get_redis_client
from ...utils.telegram import validate_init_data

router = APIRouter()


@router.websocket("/ws/tasks")
async def task_updates(websocket: WebSocket):
    init_data = websocket.query_params.get("init_data")
    if not init_data:
        await websocket.close(code=4001)
        return

    try:
        validate_init_data(init_data)
    except Exception:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    redis = get_redis_client()
    pubsub = redis.pubsub()
    await pubsub.subscribe("tasks:updates")

    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            if message and message["type"] == "message":
                await websocket.send_text(message["data"])
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe("tasks:updates")
        await pubsub.close()

