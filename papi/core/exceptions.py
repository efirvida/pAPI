from typing import Any, Dict, Optional

from fastapi import status


class APIException(Exception):
    def __init__(
        self,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        message: str,
        code: str = "ERROR",
        detail: Optional[Any] = None,
        headers: Optional[Dict[str, str]] = None,  # <- Agregado
    ):
        self.status_code = status_code
        self.message = message
        self.code = code
        self.detail = detail
        self.headers = headers
        super().__init__(message)
