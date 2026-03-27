# src/algo_studio/core/quota/exceptions.py
"""Quota-related exceptions."""


class QuotaError(Exception):
    """Base exception for quota errors."""
    pass


class QuotaExceededError(QuotaError):
    """Raised when quota is exceeded."""

    def __init__(self, message: str, quota_id: str = None, usage: dict = None):
        super().__init__(message)
        self.quota_id = quota_id
        self.usage = usage


class QuotaNotFoundError(QuotaError):
    """Raised when quota is not found."""

    def __init__(self, message: str, quota_id: str = None, scope: str = None, scope_id: str = None):
        super().__init__(message)
        self.quota_id = quota_id
        self.scope = scope
        self.scope_id = scope_id


class OptimisticLockError(QuotaError):
    """Raised when optimistic lock fails due to concurrent modification."""

    def __init__(self, message: str, quota_id: str = None, expected_version: int = None, actual_version: int = None):
        super().__init__(message)
        self.quota_id = quota_id
        self.expected_version = expected_version
        self.actual_version = actual_version


class InheritanceValidationError(QuotaError):
    """Raised when quota inheritance validation fails."""

    def __init__(self, message: str, quota_id: str = None, chain: list = None):
        super().__init__(message)
        self.quota_id = quota_id
        self.chain = chain or []
