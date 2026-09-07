from fastapi import APIRouter, HTTPException

from app.watcher.scheduler import CycleSummary, WatchCycleAlreadyRunning, WatcherStatus, get_watcher_service

router = APIRouter(tags=["watcher"])


@router.get("/watcher/status", response_model=WatcherStatus)
def watcher_status():
    return get_watcher_service().status


@router.post("/watcher/run-now", response_model=CycleSummary)
async def watcher_run_now():
    try:
        return await get_watcher_service().run_cycle()
    except WatchCycleAlreadyRunning:
        raise HTTPException(status_code=409, detail="watch cycle already running")
