from datetime import datetime, timezone
from typing import List, Tuple

import jwt

from user_auth_system.config import security
from user_auth_system.schemas.auth import KeyRotation

KEY_ROTATION_CONFIG: KeyRotation = security.key_rotation


class KeyManager:
    """Manages JWT key rotation with historical key support.

    Attributes:
        _keys: List of tuples containing (key, creation_timestamp)
        _current_key_index: Index of the currently active key
        _last_rotation: Timestamp of the last key rotation

    Methods:
        rotate_key: Generates a new signing key and updates key history
        should_rotate: Checks if key rotation is due based on configuration
    """

    _keys: List[Tuple[str, datetime]] = []
    _current_key_index: int = -1

    def __init__(self):
        """Initializes the key manager with the initial secret key."""
        self._keys = [(security.secret_key, datetime.now(timezone.utc))]
        self._current_key_index = 0
        self._last_rotation = datetime.now(timezone.utc)

    @property
    def current_key(self) -> str:
        """Gets the currently active signing key.

        Returns:
            str: The active JWT signing key
        """
        return self._keys[self._current_key_index][0]

    @property
    def all_keys(self) -> List[Tuple[str, datetime]]:
        """Gets all historical keys with their creation timestamps.

        Returns:
            List[Tuple[str, datetime]]: All managed keys with timestamps
        """
        return self._keys

    def rotate_key(self):
        """Generates a new signing key and updates key history.

        Maintains a limited history of keys based on configuration and
        updates the current key index to the newly generated key.
        """
        new_key = jwt.utils.base64url_encode(jwt.utils.get_random_bytes(64)).decode()
        self._keys.append((new_key, datetime.now(timezone.utc)))
        self._current_key_index = len(self._keys) - 1
        self._last_rotation = datetime.now(timezone.utc)

        # Prune old keys
        if len(self._keys) > KEY_ROTATION_CONFIG.max_historical_keys:
            self._keys.pop(0)
            self._current_key_index -= 1

    def should_rotate(self) -> bool:
        """Determines if key rotation is due based on rotation interval.

        Returns:
            bool: True if rotation is needed, False otherwise
        """
        time_since_last_rotation = datetime.now(timezone.utc) - self._last_rotation
        return (
            time_since_last_rotation.days >= KEY_ROTATION_CONFIG.rotation_interval_days
        )


key_manager = KeyManager()
