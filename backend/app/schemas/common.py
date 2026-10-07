"""Shared schema building blocks."""

from __future__ import annotations

from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    """Base for response models read directly from ORM objects."""

    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    """Simple acknowledgement payload."""

    message: str
    detail: Optional[str] = None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class BulkResult(BaseModel):
    """Outcome of an operation affecting multiple records."""

    processed: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)
    errors: List[str] = Field(default_factory=list)
