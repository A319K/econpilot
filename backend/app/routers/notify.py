from fastapi import APIRouter
from pydantic import BaseModel

from app.notify.factory import get_notifier

router = APIRouter(tags=["notify"])


class NotifyTestResult(BaseModel):
    success: bool
    adapter: str


@router.post("/notify/test", response_model=NotifyTestResult)
async def notify_test():
    notifier = get_notifier()
    success = await notifier.send("EconPilot test notification", "This is a test message from EconPilot.")
    return NotifyTestResult(success=success, adapter=notifier.name)
