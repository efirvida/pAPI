import base64
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Tuple

from fastapi import HTTPException, status
from loguru import logger
from pydantic import SecretStr
from sqlalchemy.future import select

from papi.core.db import get_sql_session
from user_auth_system.config import security
from user_auth_system.models.jwt_key import JWTKey
from user_auth_system.schemas.auth import KeyRotation

# Configuration constants
KEY_ROTATION_CONFIG: KeyRotation = security.key_rotation
DEFAULT_BASE_KEY = security.secret_key
DEFAULT_KEY_ID = "default"


class KeyManager:
    """
    Manages JWT signing keys with support for key rotation and historical key storage.

    This class handles:
    - Initial key loading from database or default configuration
    - Periodic key rotation based on configured intervals
    - Key pruning to maintain historical key limits
    - Key retrieval by Key ID (kid)

    When key rotation is disabled, a single static key is used for all operations.

    Attributes:
        _keys: List of tuples (key_string, creation_datetime)
        _current_key_index: Index of the active key in _keys
        _last_rotation: Timestamp of last key rotation
        _session: Database session for key persistence
    """

    def __init__(self) -> None:
        """Initializes the KeyManager with empty state."""
        self._keys: List[Tuple[str, datetime]] = []
        self._current_key_index: int = -1
        self._last_rotation: datetime = datetime.now(timezone.utc)

    async def initialize(self) -> None:
        """
        Initializes key manager by loading keys from database or creating initial key.

        If key rotation is disabled:
        - Uses the default base key from configuration
        - Sets key ID to "default"

        If key rotation is enabled:
        - Loads existing keys from database
        - Creates initial key if no keys exist
        - Sets current key to the most recent

        Args:
            session: Database session for key operations

        Raises:
            RuntimeError: If database operations fail during initialization
        """

        if not security.key_rotation.enabled:
            self._setup_static_key()
            logger.info("Key rotation disabled - using static key")
            return

        await self._load_keys_from_database()

    def _setup_static_key(self) -> None:
        """Configures manager to use static key from configuration."""
        now = datetime.now(timezone.utc)

        if isinstance(DEFAULT_BASE_KEY, SecretStr):
            key_value = DEFAULT_BASE_KEY.get_secret_value()
        else:
            key_value = DEFAULT_BASE_KEY

        self._keys = [(key_value, now)]
        self._current_key_index = 0
        self._last_rotation = now

    async def _load_keys_from_database(self) -> None:
        """Loads keys from database or creates initial key if none exist."""
        try:
            async with get_sql_session() as session:
                result = await session.execute(select(JWTKey).order_by(JWTKey.id.asc()))
                db_keys = result.scalars().all()

            if db_keys:
                self._keys = [(row.key, row.created_at) for row in db_keys]
                self._current_key_index = len(self._keys) - 1
                self._last_rotation = self._keys[-1][1]
                logger.info(f"Loaded {len(self._keys)} existing keys from database")
            else:
                await self._create_initial_key()
        except Exception as e:
            logger.critical(f"Key initialization failed: {str(e)}")
            raise RuntimeError("Key manager initialization failed") from e

    async def _create_initial_key(self) -> None:
        """Creates and persists initial key in database."""
        now = datetime.now(timezone.utc)

        if isinstance(DEFAULT_BASE_KEY, SecretStr):
            key_value = DEFAULT_BASE_KEY.get_secret_value()
        else:
            key_value = DEFAULT_BASE_KEY

        self._keys = [(key_value, now)]
        self._current_key_index = 0
        self._last_rotation = now

        base_key_record = JWTKey(key=key_value, created_at=now)
        async with get_sql_session() as session:
            session.add(base_key_record)
            await session.commit()
        logger.info("Created initial key from configuration")

    @property
    def current_key(self) -> str:
        """
        Retrieves the current active signing key.

        Returns:
            Current active key string

        Raises:
            RuntimeError: If manager is not initialized
        """
        if not self._keys:
            raise RuntimeError("KeyManager is not initialized")

        key_value = self._keys[self._current_key_index][0]

        return key_value

    @property
    def current_kid(self) -> str:
        """
        Retrieves Key ID (kid) of the current active key.

        Returns:
            "default" when rotation disabled, otherwise stringified index
        """
        if not security.key_rotation.enabled:
            return DEFAULT_KEY_ID

        return str(self._current_key_index)

    async def rotate_key(self) -> None:
        """
        Rotates the signing key and persists to database.

        Steps:
        1. Generate new cryptographically secure key
        2. Store in database
        3. Update internal state
        4. Prune excess historical keys

        Raises:
            RuntimeError: If rotation fails or database operations error
        """
        if not security.key_rotation.enabled:
            logger.warning("Key rotation attempted while disabled")
            return

        try:
            new_key = self._generate_secure_key()
            now = datetime.now(timezone.utc)

            # Persist new key
            new_jwt_key = JWTKey(key=new_key, created_at=now)
            async with get_sql_session() as session:
                session.add(new_jwt_key)
                await session.commit()

            # Update state
            self._keys.append((new_key, now))
            self._current_key_index = len(self._keys) - 1
            self._last_rotation = now

            # Maintain historical key limit
            await self._prune_old_keys()

            logger.info(f"Rotated key (new kid: {self.current_kid})")
        except Exception as e:
            logger.critical(f"Key rotation failed: {str(e)}")
            raise RuntimeError("Key rotation aborted") from e

    def _generate_secure_key(self) -> str:
        """Generates a new base64-encoded cryptographically secure key."""
        key_bytes = secrets.token_bytes(64)
        return base64.urlsafe_b64encode(key_bytes).decode()

    async def _prune_old_keys(self) -> None:
        """Removes oldest keys exceeding historical key limit."""
        if not security.key_rotation.enabled:
            return

        max_keys = KEY_ROTATION_CONFIG.max_historical_keys
        if len(self._keys) <= max_keys:
            return

        # Calculate keys to remove
        excess_count = len(self._keys) - max_keys
        oldest_allowed_time = self._keys[excess_count][1]

        # Remove from database
        async with get_sql_session() as session:
            await session.execute(
                JWTKey.__table__.delete().where(JWTKey.created_at < oldest_allowed_time)
            )
            await session.commit()

        # Update in-memory state
        self._keys = self._keys[excess_count:]
        self._current_key_index = len(self._keys) - 1

        logger.info(f"Pruned {excess_count} historical keys")

    def should_rotate(self) -> bool:
        """
        Determines if key rotation is needed based on rotation interval.

        Returns:
            True if rotation interval has elapsed since last rotation
        """
        if not security.key_rotation.enabled:
            return False

        rotation_interval = timedelta(days=KEY_ROTATION_CONFIG.rotation_interval_days)
        time_since_rotation = datetime.now(timezone.utc) - self._last_rotation
        return time_since_rotation >= rotation_interval

    def get_key_by_kid(self, kid: str) -> str:
        """
        Retrieves signing key by Key ID (kid).

        Args:
            kid: Key ID string from JWT header

        Returns:
            Corresponding signing key

        Raises:
            HTTPException: For invalid/missing keys (401 Unauthorized)
        """
        # Handle static key scenario
        if not security.key_rotation.enabled:
            if kid == DEFAULT_KEY_ID:
                return self._keys[0][0] if self._keys else ""

            logger.warning(f"Invalid KID '{kid}' for static key configuration")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
            )

        # Handle key rotation scenario
        try:
            index = int(kid)
            if 0 <= index < len(self._keys):
                return self._keys[index][0]

            logger.warning(f"Out-of-range KID requested: {kid}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token signature",
            )
        except (ValueError, TypeError):
            logger.warning(f"Malformed KID format: {kid}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Malformed token header",
            )


# Global instance for application-wide key management
key_manager = KeyManager()
