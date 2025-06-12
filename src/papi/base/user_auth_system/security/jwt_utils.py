from typing import Optional

import jwt
from fastapi import HTTPException, status
from loguru import logger

from user_auth_system.config import security

from .key_manager import key_manager


async def decode_jwt(token: str, key: Optional[str] = None) -> dict:
    """Decodes and validates a JWT with comprehensive security checks.

    Args:
        token: JWT to decode
        key: Optional specific key to use for verification

    Returns:
        dict: Decoded JWT payload

    Raises:
        jwt.InvalidSignatureError: If signature verification fails
        HTTPException: For other JWT validation failures

    Validates:
        - Signature
        - Expiration
        - Issuer
        - Audience
        - Not-before time
        - Required claims
    """
    key = key or key_manager.current_key
    return jwt.decode(
        token,
        key,
        algorithms=[security.hash_algorithm],
        audience=security.token_audience,
        issuer=security.token_issuer,
        options={
            "require": ["exp", "iat", "sub", "iss", "aud", "jti"],
            "verify_signature": True,
            "verify_aud": True,
            "verify_iss": True,
            "verify_exp": True,
            "verify_nbf": True,
        },
        leeway=30,  # 30 seconds leeway for clock skew
    )


async def try_historical_keys(token: str) -> dict:
    """Attempts to decode a token with historical signing keys.

    Args:
        token: JWT to decode

    Returns:
        dict: Decoded JWT payload

    Raises:
        HTTPException: If no valid key is found for the token

    Prioritizes keys based on the 'kid' (Key ID) header if present,
    then tries all historical keys in sequence.
    """
    kid = jwt.get_unverified_header(token).get("kid")
    keys_to_try = []

    # Prioritize key by KID if available
    if kid and int(kid) < len(key_manager.all_keys):
        keys_to_try.append(key_manager.all_keys[int(kid)][0])

    # Try all historical keys
    keys_to_try.extend([
        key for key, _ in key_manager.all_keys if key not in keys_to_try
    ])

    for key in keys_to_try:
        try:
            return await decode_jwt(token, key)
        except jwt.InvalidSignatureError:
            continue

    logger.error("Token signature invalid with all keys")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid token signature",
    )
