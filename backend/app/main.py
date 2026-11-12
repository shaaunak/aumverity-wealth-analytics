from contextlib import asynccontextmanager
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.schemas.common import ErrorDetail, ErrorEnvelope

settings = get_settings()
configure_logging(settings.LOG_LEVEL)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    logger.info(
        "Starting %s v%s (env=%s, calc=%s, currency=%s, data=%s)",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.APP_ENV,
        settings.CALCULATION_VERSION,
        settings.REPORTING_CURRENCY,
        settings.DATA_CLASSIFICATION,
    )
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Wealth Intelligence & Asset Movement Analytics. "
        "All data is SYNTHETIC for analytical demonstration."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=f"HTTP_{exc.status_code}", message=str(exc.detail)),
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    envelope = ErrorEnvelope(
        error=ErrorDetail(
            code="VALIDATION_ERROR",
            message="Invalid request parameters",
            details=exc.errors(),
        ),
        request_id=request.headers.get("X-Request-ID"),
    )
    return JSONResponse(status_code=422, content=envelope.model_dump())


app.include_router(health_router)
app.include_router(v1_router)
