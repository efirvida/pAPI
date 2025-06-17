from datetime import datetime

from pydantic import BaseModel


class Device(BaseModel):
    session_id: str
    device_id: str
    user_agent: str
    expires_at: datetime
    created_at: datetime
