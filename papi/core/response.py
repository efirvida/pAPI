import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from papi.core.models.response import DEFAULT_ERROR_CODE, APIError, APIResponse, Meta


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
            timestamp=datetime.now(tz=timezone.utc).isoformat(timespec="seconds") + "Z",
            requestId=str(uuid.uuid4()),
        ),
    )
