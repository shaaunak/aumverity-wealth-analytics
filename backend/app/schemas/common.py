from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class DecimalModel(BaseModel):
    """Base schema serializing Decimal values as exact strings to preserve financial precision."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: lambda v: f"{v:.2f}"},
    )


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PaginatedResponse(DecimalModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail
    request_id: str | None = None
