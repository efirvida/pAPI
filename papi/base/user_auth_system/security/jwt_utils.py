import jwt
from fastapi import HTTPException, status
from jwt import get_unverified_header
from loguru import logger

from user_auth_system.config import security
from user_auth_system.security.key_manager import key_manager


def get_signing_key_by_kid(kid: str) -> str:
    """
    Retrieves the signing key associated with a Key ID (kid).

    Args:
        kid: Key identifier from JWT header

    Returns:
        Corresponding signing key

    Raises:
        HTTPException: 401 for invalid/missing kid
    """
    if not kid:
        logger.warning("Missing KID in token header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature"
        )

    try:
        return key_manager.get_key_by_kid(kid)
    except HTTPException:
        logger.warning(f"Invalid KID in token: {kid}")
        raise
    except Exception as e:
        logger.critical(f"Key retrieval failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation error",
        )


def validate_token(token: str, expected_type: str) -> dict:
    """
    Validates a JWT token with comprehensive security checks.

    Verification includes:
    1. Token structure and header
    2. Key ID retrieval
    3. Cryptographic signature
    4. Standard claims (exp, iat, nbf, iss, aud)
    5. Required custom claims (jti, sub, device_id for refresh)
    6. Token type verification

    Args:
        token: JWT token string
        expected_type: Expected token type ('access' or 'refresh')

    Returns:
        Decoded token payload

    Raises:
        HTTPException: For any validation failure with appropriate status code
    """
    try:
        # Step 1: Basic token structure validation
        if not token or len(token) < 50:
            raise ValueError("Invalid token structure")

        # Step 2: Decode header to get Key ID
        header = get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise jwt.InvalidAlgorithmError("Missing KID in token header")

        # Step 3: Retrieve signing key
        key = get_signing_key_by_kid(kid)

        # Step 4: Decode and verify token
        payload = jwt.decode(
            token,
            key,
            algorithms=[security.hash_algorithm],
            audience=security.token_audience,
            issuer=security.token_issuer,
            options={
                "require": ["exp", "iat", "nbf", "iss", "aud", "jti", "sub"],
                "verify_signature": True,
                "verify_aud": True,
                "verify_iss": True,
                "verify_exp": True,
                "verify_nbf": True,
            },
            leeway=30,  # 30 seconds leeway for clock skew
        )

        # Step 5: Verify token type
        token_type = payload.get("typ")
        if token_type != expected_type:
            logger.warning(
                f"Token type mismatch: expected {expected_type}, got {token_type}"
            )
            raise ValueError("Invalid token type")

        # Step 6: Verify required claims for specific token types
        if expected_type == "refresh" and "device_id" not in payload:
            logger.error("Refresh token missing device_id claim")
            raise ValueError("Missing required claim: device_id")

        return payload

    except jwt.ExpiredSignatureError:
        logger.info(f"Expired {expected_type} token presented")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"{expected_type.capitalize()} token expired",
        )
    except jwt.InvalidAudienceError:
        logger.warning(f"Invalid audience in {expected_type} token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience"
        )
    except jwt.InvalidIssuerError:
        logger.warning(f"Invalid issuer in {expected_type} token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer"
        )
    except jwt.ImmatureSignatureError:
        logger.info(f"Premature {expected_type} token usage")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token not yet valid"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid {expected_type} token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
    except ValueError as e:
        logger.warning(f"Token validation failed: {str(e)}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected token validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token validation failed",
        )
