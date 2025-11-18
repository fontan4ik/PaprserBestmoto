from fastapi import APIRouter

from .routes import (
    admin,
    auth,
    export,
    files,
    realtime,
    stats,
    tasks,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(stats.router, prefix="/admin/stats", tags=["stats"])
api_router.include_router(realtime.router, tags=["realtime"])

