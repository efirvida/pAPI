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


def create_response(
    data: Any = None,
    success: bool = True,
    message: Optional[str] = None,
    error: Optional[Dict[str, Any]] = None,
) -> APIResponse:
    """
    Create a standardized API response in the `APIResponse` format.

    This function generates a consistent response object containing success status,
    optional data, a message, error details (if any), and metadata such as a timestamp
    and a unique request ID. It is designed to be used as a common return structure
    for all API endpoints.

    Parameters
    ----------
    data : Any, optional
        The payload to include in the response if `success` is True.
    success : bool, default=True
        Indicates whether the request was successful.
    message : str, optional
        An optional human-readable message to include in the response.
    error : dict, optional
        A dictionary with error details if `success` is False. Expected keys:
            - 'code': str — application-specific error code
            - 'message': str — short error message
            - 'detail': Any — additional error context
            - 'status_code': int — corresponding HTTP status code

    Returns
    -------
    APIResponse
        A structured response object ready to be serialized and returned from a FastAPI route.
    """
    error_obj: Optional[APIError] = None

    if not success and error:
        error_obj = APIError(
            code=error.get("code", "ERROR"),
            detail=error.get("detail"),
            message=error.get("message", "Internal server error"),
            status_code=error.get("status_code", DEFAULT_ERROR_CODE),
        )

    return APIResponse(
        success=success,
        message=message,
        data=data if success else None,
        error=error_obj,
        meta=Meta(
            timestamp=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            requestId=str(uuid.uuid4()),
        ),
    )
