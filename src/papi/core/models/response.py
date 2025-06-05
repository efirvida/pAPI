import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import status
from pydantic import BaseModel

DEFAULT_ERROR_CODE = status.HTTP_400_BAD_REQUEST


class Meta(BaseModel):
    timestamp: str
    requestId: str


class APIError(BaseModel):
    status_code: int
    detail: Optional[Any] = None
    message: Optional[str] = ""
    code: str = "ERROR"


class APIResponse(BaseModel):
    success: bool
    message: Optional[str]
    data: Optional[Any]
    error: Optional[APIError]
    meta: Meta


def create_response(
    data: Any = None,
    success: bool = True,
    message: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
) -> APIResponse:
    if not success and error:
        error_obj = APIError(
            code=error.get("code", "ERROR"),
            detail=error.get("detail", None),
            message=error.get("message", "Internal server error"),
            status_code=error.get("status_code", DEFAULT_ERROR_CODE),
        )
    else:
        error_obj = None

    return APIResponse(
        success=success,
        message=message,
        data=data if success else None,
        error=error_obj,
        meta=Meta(
            timestamp=datetime.utcnow().isoformat(),
            requestId=str(uuid.uuid4()),
        ),
    )
