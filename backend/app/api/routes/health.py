from datetime import UTC, datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.session import check_database_connection

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    environment: str
    calculation_version: str
    reporting_currency: str
    data_classification: str
    timestamp_utc: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    detail: str | None = None
    timestamp_utc: str


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def health_check() -> HealthResponse:
    """Liveness probe returning application metadata and analytical configuration."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.APP_ENV,
        calculation_version=settings.CALCULATION_VERSION,
        reporting_currency=settings.REPORTING_CURRENCY,
        data_classification=settings.DATA_CLASSIFICATION,
        timestamp_utc=datetime.now(UTC).isoformat(),
    )


@router.get("/ready", response_model=ReadinessResponse)
def readiness_check() -> JSONResponse:
    """Readiness probe verifying live PostgreSQL connectivity."""
    is_connected, error = check_database_connection()
    timestamp = datetime.now(UTC).isoformat()

    if is_connected:
        payload = ReadinessResponse(
            status="ready",
            database="connected",
            timestamp_utc=timestamp,
        )
        return JSONResponse(status_code=status.HTTP_200_OK, content=payload.model_dump())

    payload = ReadinessResponse(
        status="not_ready",
        database="disconnected",
        detail=error,
        timestamp_utc=timestamp,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )
