# src/algo_studio/api/auth.py
"""Authentication utilities with bcrypt password hashing.

This module provides password hashing and verification utilities
using bcrypt with a cost factor of 12 (industry standard balance
between security and performance).
"""

import bcrypt

# Bcrypt cost factor - industry standard balance between security and performance
# Higher values are more secure but slower
# cost=12 is the current recommendation (OWASP 2023)
BCRYPT_COST = 12


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with cost=12.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hashed password string
    """
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=BCRYPT_COST)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash.

    Args:
        password: Plain text password to verify
        password_hash: Bcrypt hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_bytes = password.encode("utf-8")
        hash_bytes = password_hash.encode("utf-8")
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception:
        # Invalid hash format or other error
        return False


def verify_password_legacy(password: str, password_hash: str) -> bool:
    """Verify password with legacy hash formats for backwards compatibility.

    Supports:
    - Bcrypt hashes (new format)
    - Plain MD5 hashes (legacy, will be migrated)

    Args:
        password: Plain text password to verify
        password_hash: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    # Try standard bcrypt verification first
    if verify_password(password, password_hash):
        return True

    # Legacy MD5 support (for migration only)
    # TODO: Remove this after all users have migrated to bcrypt
    if password_hash.startswith("md5:"):
        import hashlib

        expected_hash = hashlib.md5(password.encode()).hexdigest()
        return expected_hash == password_hash[4:]

    return False
