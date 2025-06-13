import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Optional

from loguru import logger

from papi.core.db import get_sql_session
from user_auth_system.models import AuditLog


async def log_security_event_async(event_type: str, details: Optional[Dict] = None):
    """
    Asynchronously logs a security-relevant event in the audit database.

    Use this function directly in async contexts (e.g., inside FastAPI routes).

    Args:
        event_type (str): A string indicating the type of the event.
        details (Optional[Dict]): Additional context or metadata.
    """
    try:
        await _log_event_async(event_type, details)
    except Exception as e:
        logger.exception(f"Failed to log audit event: {e}")


def log_security_event_sync(event_type: str, details: Optional[Dict] = None):
    """
    Synchronously logs a security-relevant event using an isolated event loop.

    Safe to use in background tasks or non-async contexts.

    Args:
        event_type (str): A string indicating the type of the event.
        details (Optional[Dict]): Additional context or metadata.
    """
    try:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_log_event_async(event_type, details))
    except Exception as e:
        logger.exception(f"Failed to log audit event: {e}")
    finally:
        loop.close()


async def _log_event_async(event_type: str, details: Optional[Dict]):
    """
    Internal coroutine to persist the audit log into the database.

    Args:
        event_type (str): The type of event to log.
        details (Optional[Dict]): Additional details, serialized to JSON.
    """
    if not event_type:
        logger.error("Attempted to log event with empty event_type")
        return
        
    # Sanitize and validate details before logging
    if details:
        # Remove any sensitive information
        sanitized_details = {
            k: v for k, v in details.items() 
            if not any(sensitive in k.lower() 
                      for sensitive in ['password', 'token', 'secret', 'key', 'auth'])
        }
    else:
        sanitized_details = {}

    try:
        async with get_sql_session() as session:
            event = AuditLog(
                event_type=event_type[:255],  # Prevent overflow
                details=json.dumps(sanitized_details),
                timestamp=datetime.now(timezone.utc),
            )
            session.add(event)
            await session.commit()
    except Exception as e:
        # Don't expose internal errors in logs
        logger.error("Audit log persistence failed")
