# src/algo_studio/core/deploy/credential_store.py
"""Credential storage and management for AlgoStudio.

This module provides secure storage of deployment credentials (SSH passwords,
keys, etc.) in Redis with encryption.

Usage:
    store = CredentialStore()
    credential_id = await store.save_credential(user_id, name, credential_data)
    credentials = await store.list_credentials(user_id)
    await store.delete_credential(credential_id)
"""

import base64
import hashlib
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import redis.asyncio as redis
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


# ==============================================================================
# Encryption Key Management
# ==============================================================================

def _get_encryption_key() -> bytes:
    """Get encryption key for credentials.

    Uses CREDENTIAL_ENCRYPTION_KEY env var if set, otherwise derives from
    RBAC_SECRET_KEY.

    Raises:
        RuntimeError: If neither CREDENTIAL_ENCRYPTION_KEY nor RBAC_SECRET_KEY is set.
            This prevents data loss from temporary keys on restart.
    """
    key = os.environ.get("CREDENTIAL_ENCRYPTION_KEY")
    if key:
        # If it's a raw string, encode it; if bytes, use directly
        return key.encode() if isinstance(key, str) else key

    rbac_key = os.environ.get("RBAC_SECRET_KEY")
    if rbac_key:
        # Derive a Fernet-compatible key from the RBAC secret
        # sha256 produces 32 raw bytes, which we then base64 encode for Fernet
        digest = hashlib.sha256(rbac_key.encode()).digest()
        return base64.urlsafe_b64encode(digest)

    # Fail fast - credentials would be permanently lost on restart
    raise RuntimeError(
        "CREDENTIAL_ENCRYPTION_KEY or RBAC_SECRET_KEY must be set. "
        "Credentials cannot be stored without a persistent encryption key. "
        "Set CREDENTIAL_ENCRYPTION_KEY environment variable with a Fernet-compatible key, "
        "or ensure RBAC_SECRET_KEY is set."
    )


# Global Fernet instance
_fernet = Fernet(_get_encryption_key())


def _encrypt_value(value: str) -> str:
    """Encrypt a string value.

    Args:
        value: Plain text string to encrypt

    Returns:
        Encrypted string (base64 encoded)
    """
    return _fernet.encrypt(value.encode()).decode()


def _decrypt_value(encrypted: str) -> str:
    """Decrypt an encrypted string.

    Args:
        encrypted: Encrypted string (base64 encoded)

    Returns:
        Decrypted plain text string

    Raises:
        InvalidToken: If decryption fails
    """
    return _fernet.decrypt(encrypted.encode()).decode()


# ==============================================================================
# Credential Data Model
# ==============================================================================

@dataclass
class Credential:
    """Represents a stored credential.

    Attributes:
        credential_id: Unique identifier for the credential
        user_id: ID of the user who owns this credential
        name: Human-readable name for the credential
        username: Username for the credential
        password: Encrypted password (stored encrypted)
        credential_type: Type of credential (password, ssh_key, etc.)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    credential_id: str
    user_id: str
    name: str
    username: str
    password: str  # Encrypted
    credential_type: str = "password"
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self, include_password: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization.

        Args:
            include_password: If True, decrypt and include password

        Returns:
            Dictionary representation
        """
        result = {
            "credential_id": self.credential_id,
            "user_id": self.user_id,
            "name": self.name,
            "username": self.username,
            "credential_type": self.credential_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_password:
            try:
                result["password"] = _decrypt_value(self.password)
            except InvalidToken:
                result["password"] = None
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Credential":
        """Create Credential from dictionary.

        Args:
            data: Dictionary with credential data

        Returns:
            Credential instance
        """
        return cls(
            credential_id=data["credential_id"],
            user_id=data["user_id"],
            name=data["name"],
            username=data["username"],
            password=data["password"],
            credential_type=data.get("credential_type", "password"),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


# ==============================================================================
# Credential Store
# ==============================================================================

class CredentialStore:
    """Manages encrypted credential storage in Redis.

    Redis Key Structure:
    - deploy:credentials:{credential_id} - Individual credential data
    - deploy:credentials:user:{user_id} - Set of credential IDs for a user
    """

    REDIS_CREDENTIAL_PREFIX = "deploy:credentials:"
    REDIS_USER_CREDENTIALS_PREFIX = "deploy:credentials:user:"

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6380, redis_password: Optional[str] = None):
        """Initialize credential store.

        Args:
            redis_host: Redis host address
            redis_port: Redis port number
            redis_password: Redis password for authentication (optional)
        """
        self._redis: Optional[redis.Redis] = None
        self._redis_host = redis_host
        self._redis_port = redis_port
        self._redis_password = redis_password or os.environ.get("REDIS_PASSWORD")

    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            self._redis = redis.Redis(
                host=self._redis_host,
                port=self._redis_port,
                password=self._redis_password,
                decode_responses=True,
            )
        return self._redis

    def _generate_credential_id(self) -> str:
        """Generate a unique credential ID.

        Returns:
            Credential ID in format cred_<timestamp>_<random>
        """
        timestamp = int(time.time() * 1000)
        random_part = secrets.token_hex(8)
        return f"cred_{timestamp}_{random_part}"

    async def save_credential(
        self,
        user_id: str,
        name: str,
        username: str,
        password: str,
        credential_type: str = "password",
    ) -> str:
        """Save a new credential.

        Args:
            user_id: ID of the user who owns this credential
            name: Human-readable name for the credential
            username: Username for the credential
            password: Plain text password to encrypt and store
            credential_type: Type of credential (password, ssh_key, etc.)

        Returns:
            The generated credential_id

        Raises:
            ValueError: If required fields are missing
        """
        if not user_id:
            raise ValueError("user_id is required")
        if not name:
            raise ValueError("name is required")
        if not username:
            raise ValueError("username is required")
        if not password:
            raise ValueError("password is required")

        credential_id = self._generate_credential_id()

        # Encrypt the password before storage
        encrypted_password = _encrypt_value(password)

        credential = Credential(
            credential_id=credential_id,
            user_id=user_id,
            name=name,
            username=username,
            password=encrypted_password,
            credential_type=credential_type,
        )

        r = await self._get_redis()

        # Store credential data
        credential_key = f"{self.REDIS_CREDENTIAL_PREFIX}{credential_id}"
        await r.set(credential_key, json.dumps(credential.to_dict()))

        # Add to user's credential set
        user_key = f"{self.REDIS_USER_CREDENTIALS_PREFIX}{user_id}"
        await r.sadd(user_key, credential_id)

        logger.info(f"Saved credential {credential_id} for user {user_id}")
        return credential_id

    async def list_credentials(self, user_id: str) -> List[Dict[str, Any]]:
        """List all credentials for a user.

        Args:
            user_id: ID of the user

        Returns:
            List of credential metadata (without passwords)
        """
        if not user_id:
            raise ValueError("user_id is required")

        r = await self._get_redis()

        # Get all credential IDs for this user
        user_key = f"{self.REDIS_USER_CREDENTIALS_PREFIX}{user_id}"
        credential_ids = await r.smembers(user_key)

        credentials = []
        for cred_id in credential_ids:
            credential_key = f"{self.REDIS_CREDENTIAL_PREFIX}{cred_id}"
            data = await r.get(credential_key)
            if data:
                try:
                    cred = Credential.from_dict(json.loads(data))
                    # Don't include encrypted password in list view
                    credentials.append({
                        "id": cred.credential_id,
                        "name": cred.name,
                        "username": cred.username,
                        "type": cred.credential_type,
                        "created_at": cred.created_at.isoformat(),
                    })
                except (json.JSONDecodeError, KeyError):
                    logger.warning(f"Invalid credential data for {cred_id}")
                    continue

        return credentials

    async def get_credential(self, credential_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific credential with decrypted password.

        Args:
            credential_id: ID of the credential
            user_id: ID of the user (for ownership verification)

        Returns:
            Credential data including decrypted password, or None if not found
        """
        r = await self._get_redis()

        credential_key = f"{self.REDIS_CREDENTIAL_PREFIX}{credential_id}"
        data = await r.get(credential_key)

        if not data:
            return None

        try:
            cred = Credential.from_dict(json.loads(data))

            # Verify ownership
            if cred.user_id != user_id:
                logger.warning(
                    f"User {user_id} attempted to access credential {credential_id} "
                    f"owned by {cred.user_id}"
                )
                return None

            # Return with decrypted password
            return cred.to_dict(include_password=True)

        except (json.JSONDecodeError, KeyError, InvalidToken) as e:
            logger.error(f"Failed to get credential {credential_id}: {e}")
            return None

    async def delete_credential(self, credential_id: str, user_id: str) -> bool:
        """Delete a credential.

        Args:
            credential_id: ID of the credential to delete
            user_id: ID of the user (for ownership verification)

        Returns:
            True if deleted, False if not found or not owned by user
        """
        r = await self._get_redis()

        credential_key = f"{self.REDIS_CREDENTIAL_PREFIX}{credential_id}"
        data = await r.get(credential_key)

        if not data:
            return False

        try:
            cred = Credential.from_dict(json.loads(data))

            # Verify ownership
            if cred.user_id != user_id:
                logger.warning(
                    f"User {user_id} attempted to delete credential {credential_id} "
                    f"owned by {cred.user_id}"
                )
                return False

            # Remove from user's set
            user_key = f"{self.REDIS_USER_CREDENTIALS_PREFIX}{user_id}"
            await r.srem(user_key, credential_id)

            # Delete credential data
            await r.delete(credential_key)

            logger.info(f"Deleted credential {credential_id} for user {user_id}")
            return True

        except (json.JSONDecodeError, KeyError):
            return False

    async def credential_exists(self, credential_id: str) -> bool:
        """Check if a credential exists.

        Args:
            credential_id: ID of the credential

        Returns:
            True if exists, False otherwise
        """
        r = await self._get_redis()
        credential_key = f"{self.REDIS_CREDENTIAL_PREFIX}{credential_id}"
        return await r.exists(credential_key) > 0