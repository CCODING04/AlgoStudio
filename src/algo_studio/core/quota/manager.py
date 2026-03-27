# src/algo_studio/core/quota/manager.py
"""QuotaManager - Core quota management logic."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from algo_studio.core.quota.exceptions import (
    InheritanceValidationError,
    OptimisticLockError,
    QuotaExceededError,
    QuotaNotFoundError,
)
from algo_studio.core.quota.store import QuotaScope, QuotaStoreInterface, ResourceQuota


class QuotaManager:
    """Manages resource quotas with hierarchical inheritance support.

    Supports GLOBAL -> TEAM -> USER inheritance hierarchy.
    """

    def __init__(self, store: QuotaStoreInterface):
        """Initialize QuotaManager.

        Args:
            store: Quota storage implementation
        """
        self.store = store

    def check_quota(
        self,
        user_id: str,
        team_id: Optional[str],
        requested: ResourceQuota,
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]], List[str]]:
        """Check if user/team can be allocated the requested resources.

        Args:
            user_id: User identifier
            team_id: Optional team identifier
            requested: Resource quota being requested

        Returns:
            (allowed, effective_quota, usage, reasons)
                - allowed: True if allocation is allowed
                - effective_quota: The quota that applies (with inheritance)
                - usage: Current usage for that quota
                - reasons: List of rejection reasons if not allowed
        """
        # 1. Get effective quota (with inheritance)
        quota = self._get_effective_quota(user_id, team_id)
        if not quota:
            # No quota defined - allow
            return (True, None, None, [])

        # Check if unlimited
        if self._is_unlimited(quota):
            return (True, quota, None, [])

        # 2. Get current usage
        usage = self.store.get_usage(quota["quota_id"])
        if not usage:
            # No usage record - create one implicitly
            usage = {
                "quota_id": quota["quota_id"],
                "cpu_cores_used": 0,
                "gpu_count_used": 0,
                "gpu_memory_gb_used": 0,
                "memory_gb_used": 0,
                "disk_gb_used": 0,
                "concurrent_tasks_used": 0,
                "tasks_today": 0,
                "gpu_minutes_today": 0,
                "version": 0,
            }

        # 3. Check allocation
        can_allocate, reasons = self._can_allocate(quota, usage, requested)

        return (can_allocate, quota, usage, reasons)

    def _get_effective_quota(
        self, user_id: str, team_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get effective quota considering inheritance.

        Priority: USER > TEAM > GLOBAL
        """
        # 1. Try user quota
        user_quota = self.store.get_quota_by_scope(QuotaScope.USER, user_id)
        if user_quota and not self._is_unlimited(user_quota):
            return user_quota

        # 2. Try team quota
        if team_id:
            team_quota = self.store.get_quota_by_scope(QuotaScope.TEAM, team_id)
            if team_quota and not self._is_unlimited(team_quota):
                return team_quota

        # 3. Try global quota
        global_quota = self.store.get_quota_by_scope(QuotaScope.GLOBAL, "global")
        if global_quota and not self._is_unlimited(global_quota):
            return global_quota

        return None

    def _is_unlimited(self, quota: Dict[str, Any]) -> bool:
        """Check if quota is unlimited (all limits are 0)."""
        return (
            quota.get("cpu_cores", 0) == 0
            and quota.get("gpu_count", 0) == 0
            and quota.get("gpu_memory_gb", 0.0) == 0.0
            and quota.get("memory_gb", 0.0) == 0.0
            and quota.get("disk_gb", 0.0) == 0.0
            and quota.get("concurrent_tasks", 0) == 0
        )

    def _can_allocate(
        self,
        quota: Dict[str, Any],
        usage: Dict[str, Any],
        requested: ResourceQuota,
    ) -> Tuple[bool, List[str]]:
        """Check if requested resources can be allocated.

        Returns:
            (can_allocate, reasons)
        """
        reasons = []

        # Check each resource dimension
        cpu_available = quota.get("cpu_cores", 0) - usage.get("cpu_cores_used", 0)
        if requested.cpu_cores > cpu_available:
            reasons.append(
                f"CPU cores: requested {requested.cpu_cores}, available {cpu_available}"
            )

        gpu_available = quota.get("gpu_count", 0) - usage.get("gpu_count_used", 0)
        if requested.gpu_count > gpu_available:
            reasons.append(
                f"GPU count: requested {requested.gpu_count}, available {gpu_available}"
            )

        gpu_mem_available = quota.get("gpu_memory_gb", 0.0) - usage.get("gpu_memory_gb_used", 0.0)
        if requested.gpu_memory_gb > gpu_mem_available:
            reasons.append(
                f"GPU memory: requested {requested.gpu_memory_gb}GB, "
                f"available {gpu_mem_available}GB"
            )

        mem_available = quota.get("memory_gb", 0.0) - usage.get("memory_gb_used", 0.0)
        if requested.memory_gb > mem_available:
            reasons.append(
                f"Memory: requested {requested.memory_gb}GB, available {mem_available}GB"
            )

        disk_available = quota.get("disk_gb", 0.0) - usage.get("disk_gb_used", 0.0)
        if requested.disk_gb > disk_available:
            reasons.append(
                f"Disk: requested {requested.disk_gb}GB, available {disk_available}GB"
            )

        tasks_available = quota.get("concurrent_tasks", 0) - usage.get("concurrent_tasks_used", 0)
        if requested.concurrent_tasks > tasks_available:
            reasons.append(
                f"Concurrent tasks: requested {requested.concurrent_tasks}, "
                f"available {tasks_available}"
            )

        return (len(reasons) == 0, reasons)

    def allocate_resources(
        self, quota_id: str, resources: ResourceQuota, expected_version: int = None
    ) -> bool:
        """Allocate resources (atomically increment usage).

        Args:
            quota_id: Quota to allocate from
            resources: Resources to allocate
            expected_version: Optional version for optimistic locking

        Returns:
            True if allocation succeeded

        Raises:
            QuotaNotFoundError: If quota doesn't exist
            OptimisticLockError: If version mismatch
        """
        try:
            return self.store.increment_usage(quota_id, resources, expected_version)
        except OptimisticLockError:
            raise
        except QuotaNotFoundError:
            raise

    def release_resources(self, quota_id: str, resources: ResourceQuota) -> bool:
        """Release resources (atomically decrement usage).

        Args:
            quota_id: Quota to release from
            resources: Resources to release

        Returns:
            True if release succeeded
        """
        return self.store.decrement_usage(quota_id, resources)

    def validate_inheritance(self, quota_id: str) -> Tuple[bool, List[str]]:
        """Validate quota inheritance chain.

        Checks:
        1. No cycles in inheritance chain
        2. All parent quotas exist
        3. Scope hierarchy is valid (user -> team -> global)

        Args:
            quota_id: Quota ID to validate

        Returns:
            (is_valid, error_messages)
                - is_valid: True if inheritance is valid
                - error_messages: List of error messages if invalid

        Raises:
            QuotaNotFoundError: If the quota itself doesn't exist
        """
        # First check if quota exists
        quota = self.store.get_quota(quota_id)
        if quota is None:
            raise QuotaNotFoundError(f"Quota not found: {quota_id}", quota_id=quota_id)

        errors = []

        # Get the quota's own scope
        scope = quota.get("scope")
        scope_id = quota.get("scope_id")

        # Validate scope hierarchy
        if scope == QuotaScope.USER:
            # User quota should have team parent or global parent
            parent_id = quota.get("parent_quota_id")
            if parent_id:
                parent = self.store.get_quota(parent_id)
                if parent is None:
                    errors.append(f"Parent quota not found: {parent_id}")
                elif parent["scope"] == QuotaScope.USER:
                    errors.append("User quota cannot have another user quota as parent")
        elif scope == QuotaScope.TEAM:
            # Team quota should have global parent or no parent
            parent_id = quota.get("parent_quota_id")
            if parent_id:
                parent = self.store.get_quota(parent_id)
                if parent is None:
                    errors.append(f"Parent quota not found: {parent_id}")
                elif parent["scope"] != QuotaScope.GLOBAL:
                    errors.append("Team quota must have global parent or no parent")
        elif scope == QuotaScope.GLOBAL:
            # Global quota should have no parent
            parent_id = quota.get("parent_quota_id")
            if parent_id:
                errors.append("Global quota should not have a parent")

        # Validate the full inheritance chain
        chain_valid, chain_errors = self.store.validate_inheritance_chain(quota_id)
        if not chain_valid:
            errors.extend(chain_errors)

        return (len(errors) == 0, errors)

    def validate_inheritance_or_raise(self, quota_id: str) -> None:
        """Validate quota inheritance, raising exception if invalid.

        Args:
            quota_id: Quota ID to validate

        Raises:
            InheritanceValidationError: If inheritance is invalid
            QuotaNotFoundError: If quota doesn't exist
        """
        is_valid, errors = self.validate_inheritance(quota_id)
        if not is_valid:
            chain = self.store.get_quota_inheritance_chain(quota_id)
            raise InheritanceValidationError(
                f"Invalid inheritance chain for quota {quota_id}: {'; '.join(errors)}",
                quota_id=quota_id,
                chain=chain,
            )

    def get_effective_quota_with_inheritance(
        self, user_id: str, team_id: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Get effective quota with full inheritance chain information.

        Returns quota plus chain showing inherited limits.
        """
        quota = self._get_effective_quota(user_id, team_id)
        if quota is None:
            return None

        # Build inheritance chain info
        chain = self.store.get_quota_inheritance_chain(quota["quota_id"])

        # Calculate effective limits (most specific wins)
        effective = {
            "quota_id": quota["quota_id"],
            "scope": quota["scope"],
            "scope_id": quota["scope_id"],
            "inheritance_chain": chain,
        }

        # Start with global defaults (unlimited)
        inherited = {
            "cpu_cores": 0,
            "gpu_count": 0,
            "gpu_memory_gb": 0.0,
            "memory_gb": 0.0,
            "disk_gb": 0.0,
            "concurrent_tasks": 0,
            "tasks_per_day": 0,
            "gpu_hours_per_day": 0.0,
        }

        # Apply chain from global to specific (later values override)
        for qid in chain:
            q = self.store.get_quota(qid)
            if q:
                for key in inherited:
                    val = q.get(key)
                    if val and val > 0:
                        inherited[key] = val

        effective.update(inherited)
        return effective

    def check_task_submission(
        self, user_id: str, team_id: Optional[str], task_type: str
    ) -> Tuple[bool, Optional[str]]:
        """Check if a task submission is allowed.

        Args:
            user_id: User submitting the task
            team_id: Optional team
            task_type: Type of task (train/infer/verify)

        Returns:
            (allowed, error_message)
        """
        # Determine resource requirements based on task type
        if task_type == "train":
            requested = ResourceQuota(
                concurrent_tasks=1,
                cpu_cores=4,
                gpu_count=1,
                gpu_memory_gb=8.0,
                memory_gb=16.0,
            )
        elif task_type == "infer":
            requested = ResourceQuota(
                concurrent_tasks=1,
                cpu_cores=1,
                gpu_count=0,
                memory_gb=4.0,
            )
        elif task_type == "verify":
            requested = ResourceQuota(
                concurrent_tasks=1,
                cpu_cores=1,
                gpu_count=0,
                memory_gb=2.0,
            )
        else:
            requested = ResourceQuota(concurrent_tasks=1)

        allowed, quota, usage, reasons = self.check_quota(user_id, team_id, requested)
        if not allowed:
            return (False, f"Quota exceeded: {'; '.join(reasons)}")

        return (True, None)

    def get_usage_percentage(
        self, quota: Dict[str, Any], usage: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate usage percentage for each resource dimension.

        Returns:
            Dict mapping resource name to usage percentage (0-100+)
        """
        percentages = {}

        dimensions = [
            ("cpu_cores", "cpu_cores_used"),
            ("gpu_count", "gpu_count_used"),
            ("gpu_memory_gb", "gpu_memory_gb_used"),
            ("memory_gb", "memory_gb_used"),
            ("disk_gb", "disk_gb_used"),
            ("concurrent_tasks", "concurrent_tasks_used"),
        ]

        for limit_key, used_key in dimensions:
            limit = quota.get(limit_key, 0)
            used = usage.get(used_key, 0)
            if limit > 0:
                percentages[limit_key] = (used / limit) * 100
            else:
                percentages[limit_key] = 0.0

        return percentages

    def create_quota(self, quota_data: Dict[str, Any]) -> str:
        """Create a new quota.

        Args:
            quota_data: Quota configuration

        Returns:
            The created quota_id
        """
        if "quota_id" not in quota_data:
            quota_data["quota_id"] = str(uuid.uuid4())

        self.store.create_quota(quota_data)
        return quota_data["quota_id"]

    def get_quota(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get quota by ID."""
        return self.store.get_quota(quota_id)

    def get_usage(self, quota_id: str) -> Optional[Dict[str, Any]]:
        """Get current usage for a quota."""
        return self.store.get_usage(quota_id)

    def list_quotas(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """List quotas, optionally filtered by scope."""
        return self.store.list_quotas(scope)
