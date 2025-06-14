import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import status
from pydantic import BaseModel, Field

DEFAULT_ERROR_CODE = status.HTTP_400_BAD_REQUEST


class Meta(BaseModel):
    timestamp: str = Field(..., description="ISO 8601 timestamp of the response")
    requestId: str = Field(..., description="Unique request identifier")


class APIError(BaseModel):
    status_code: int = Field(..., description="HTTP status code of the error")
    detail: Optional[Any] = Field(
        None, description="Additional details about the error"
    )
    message: str = Field(
        default="Internal server error", description="Human-readable error message"
    )
    code: str = Field(default="ERROR", description="Custom application error code")


class APIResponse(BaseModel):
    success: bool = Field(
        ..., description="Indicates whether the request was successful"
    )
    message: Optional[str] = Field(None, description="Optional message for the client")
    data: Optional[Any] = Field(None, description="Returned data if success is True")
    error: Optional[APIError] = Field(
        None, description="Error information if success is False"
    )
    meta: Meta = Field(..., description="Metadata for the response")
