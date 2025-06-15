import time
from typing import Dict, Tuple

from fastapi import HTTPException, status
from loguru import logger

# In-memory store for rate limiting
# token_hash -> (attempt_count, first_attempt_timestamp)
_rate_limit_store: Dict[str, Tuple[int, float]] = {}

# Rate limit configuration
MAX_ATTEMPTS = 5
WINDOW_SECONDS = 300  # 5 minutes
BLOCK_DURATION = 900  # 15 minutes


def _hash_token(token: str) -> str:
    """
    Creates a secure hash of the token for rate limiting.
    We don't store the actual token for security reasons.
    """
    from hashlib import sha256

    return sha256(token.encode()).hexdigest()


async def check_auth_rate_limit(token: str) -> None:
    """
    Implements a sliding window rate limiting for authentication attempts.

    Args:
        token: The authentication token to check

    Raises:
        HTTPException: If rate limit is exceeded
    """
    token_hash = _hash_token(token)
    current_time = time.time()

    # Clean up old entries
    cleanup_threshold = current_time - WINDOW_SECONDS
    _rate_limit_store.clear()

    if token_hash in _rate_limit_store:
        attempts, first_attempt = _rate_limit_store[token_hash]

        # Check if in blocking period
        if attempts >= MAX_ATTEMPTS:
            block_end = first_attempt + BLOCK_DURATION
            if current_time < block_end:
                logger.warning(
                    f"Rate limit exceeded for token hash: {token_hash[:8]}..."
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Too many authentication attempts. Try again in {int(block_end - current_time)} seconds",
                )
            else:
                # Reset after block period
                del _rate_limit_store[token_hash]

        # Update attempts within window
        if current_time - first_attempt <= WINDOW_SECONDS:
            _rate_limit_store[token_hash] = (attempts + 1, first_attempt)
        else:
            # Reset window
            _rate_limit_store[token_hash] = (1, current_time)
    else:
        # First attempt
        _rate_limit_store[token_hash] = (1, current_time)
