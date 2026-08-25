"""
Report API for Project Lucy.
"""
import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.report_engine import ReportEngine, REPORTS_DIR
from dependencies import CurrentUser, OperatorUser

router = APIRouter(prefix="/reports", tags=["reports"])
engine = ReportEngine()

REPORTS: dict[str, dict] = {}


class ReportRequest(BaseModel):
    type: str = "engagement"   # engagement | executive | credentials | technical
    format: str = "html"       # html | pdf | json
    agent_ids: list[str] | None = None
    date_range: dict | None = None


@router.post("", status_code=202)
async def generate_report(body: ReportRequest, bg: BackgroundTasks, current_user: OperatorUser) -> dict:
    import uuid
    report_id = str(uuid.uuid4())
    REPORTS[report_id] = {"status": "queued", "path": None, "error": None}
    bg.add_task(_run_report, report_id, body)
    return {"report_id": report_id, "status": "queued"}


@router.get("")
async def list_reports(current_user: CurrentUser) -> list[dict]:
    return [{"report_id": rid, **info} for rid, info in REPORTS.items()]


@router.get("/{report_id}")
async def report_status(report_id: str, current_user: CurrentUser) -> dict:
    r = REPORTS.get(report_id)
    if not r:
        raise HTTPException(404, "Report not found")
    return {"report_id": report_id, **r}


@router.get("/{report_id}/download")
async def download_report(report_id: str, current_user: CurrentUser) -> FileResponse:
    r = REPORTS.get(report_id)
    if not r or r["status"] != "done":
        raise HTTPException(404, "Report not ready")
    path = r.get("path")
    if not path or not Path(path).exists():
        raise HTTPException(410, "Report file expired")
    suffix = Path(path).suffix
    media = {
        ".json": "application/json",
        ".html": "text/html",
        ".pdf": "application/pdf",
    }.get(suffix, "application/octet-stream")
    return FileResponse(path, filename=Path(path).name, media_type=media)


async def _run_report(report_id: str, req: ReportRequest) -> None:
    REPORTS[report_id]["status"] = "building"
    try:
        result = engine.generate(req.type, req.format, req.agent_ids, req.date_range)
        REPORTS[report_id].update({"status": "done", "path": result["path"]})
    except Exception as exc:
        REPORTS[report_id].update({"status": "error", "error": str(exc)})
