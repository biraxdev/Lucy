"""Prometheus metrics exposition endpoint."""
from fastapi import APIRouter, Response

from core.metrics import get_metrics

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus scrape endpoint."""
    data = get_metrics()
    return Response(content=data, media_type="text/plain; version=0.0.4; charset=utf-8")
