"""
Screenshot Scheduler API — configure and control automatic screenshotting.
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from core.screenshot_scheduler import ScreenshotScheduler
from dependencies import OperatorUser

router = APIRouter(prefix="/screenshot-scheduler", tags=["screenshot-scheduler"])
scheduler = ScreenshotScheduler()


class SchedulerConfig(BaseModel):
    interval_minutes: int | None = Field(None, ge=1, le=1440)
    quality: int | None = Field(None, ge=10, le=100)
    max_width: int | None = Field(None, ge=320, le=3840)
    target_mode: str | None = Field(None, pattern=r"^(online|all|specific)$")
    target_agent_ids: list[str] | None = None


@router.get("/status")
async def get_status(current_user: OperatorUser = None) -> dict:
    return scheduler.get_config()


@router.put("/config")
async def update_config(body: SchedulerConfig, current_user: OperatorUser = None) -> dict:
    return scheduler.configure(
        interval_minutes=body.interval_minutes,
        quality=body.quality,
        max_width=body.max_width,
        target_mode=body.target_mode,
        target_agent_ids=body.target_agent_ids,
    )


@router.post("/start")
async def start_scheduler(current_user: OperatorUser = None) -> dict:
    return await scheduler.start()


@router.post("/stop")
async def stop_scheduler(current_user: OperatorUser = None) -> dict:
    return await scheduler.stop()


@router.post("/trigger")
async def trigger_now(current_user: OperatorUser = None) -> dict:
    return await scheduler.trigger_now()
