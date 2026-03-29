# Phase 3.5 API/Security Review Report

**From:** @architect-beta
**Date:** 2026-03-29
**To:** @coordinator
**Topic:** Phase 3.5 R9 最终评审 - API/安全评审

---

## Summary

Phase 3.5 implementation is **APPROVED WITH CONDITIONS**. Three critical security issues and several important improvements required before production deployment.

---

## 1. Dataset API Endpoints

### Status: ISSUES FOUND

#### Critical Issues

**1.1. Missing RBAC Permission Integration in Dataset Routes**

The dataset routes in `datasets.py` check authentication manually (`if not user: raise 401`) but do NOT use the `require_permission()` dependency from `rbac.py`. The RBAC middleware's `PROTECTED_ROUTES` defines permissions for datasets, but these are enforced at middleware level with prefix matching which is fragile.

Example from `datasets.py` line 155-167:
```python
async def list_datasets(...):
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    # No permission check for DATASET_READ!
```

**Recommendation:** Add explicit permission dependencies to all dataset endpoints:
```python
from algo_studio.api.middleware.rbac import require_permission, Permission

@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    user: User = Depends(require_permission(Permission.DATASET_READ)),
    ...
):
```

**1.2. list_datasets Exposes All Datasets Without Access Filtering**

The `list_datasets` endpoint (line 155-206) returns ALL active datasets regardless of user access permissions. Users can enumerate datasets they have no access to.

**Recommendation:** Filter datasets by user's access permission:
```python
# After building base query, add access filter
if not user.is_superuser:
    # Include public datasets OR datasets owned by user OR datasets user has access to
    access_subquery = select(DatasetAccess.dataset_id).where(
        DatasetAccess.user_id == user.user_id
    )
    query = query.where(
        (Dataset.is_public == True) |
        (Dataset.owner_id == user.user_id) |
        (Dataset.dataset_id.in_(access_subquery))
    )
```

**1.3. SQL Wildcard Injection in Search**

The search filter at line 174 uses:
```python
query = query.where(Dataset.name.ilike(f"%{search}%"))
```

Unescaped `%` and `_` in search terms act as SQL wildcards, potentially causing performance issues or unexpected results.

**Recommendation:** Escape wildcards before use:
```python
import re
escaped_search = re.escape(search)  # Escape %, _, etc.
query = query.where(Dataset.name.ilike(f"%{escaped_search}%"))
```

#### Important Issues

**1.4. Access Control Endpoints Don't Enforce DATASET_ADMIN Permission**

The `list_dataset_access`, `grant_dataset_access`, and `revoke_dataset_access` endpoints use `check_dataset_access(session, user, dataset_id, "admin")` which requires `admin` level in dataset_access table. However, the RBAC middleware doesn't know about this - it only has `DATASET_ADMIN` permission defined but not enforced.

**1.5. Owner Can Be Changed by Write Permission Holder**

The `update_dataset` endpoint allows modifying `owner_id` and `team_id` fields (via `DatasetUpdateRequest`). A user with `write` access can reassign dataset ownership.

**Recommendation:** Prevent non-owner/superuser from changing `owner_id`:
```python
if request.owner_id is not None and request.owner_id != dataset.owner_id:
    if not user.is_superuser and dataset.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only owner can transfer ownership")
```

---

## 2. Credential Encrypted Storage

### Status: ISSUES FOUND

#### Critical Issues

**2.1. Encryption Key Loss on Restart (WARNING in code ignored)**

`credential_store.py` lines 53-57:
```python
logger.warning(
    "No CREDENTIAL_ENCRYPTION_KEY or RBAC_SECRET_KEY set. "
    "Credentials will use a temporary key that will be lost on restart."
)
return Fernet.generate_key()
```

If neither env var is set, credentials become permanently unreadable after restart. This is a **data loss risk**.

**Recommendation:** Fail fast if no encryption key is configured:
```python
if not key and not rbac_key:
    raise RuntimeError(
        "CREDENTIAL_ENCRYPTION_KEY or RBAC_SECRET_KEY must be set. "
        "Credentials cannot be stored without persistent encryption key."
    )
```

**2.2. SSH Key Credential Type Not Properly Handled**

The code accepts `credential_type: ssh_key` but stores the entire credential in the `password` field (encrypted). For SSH keys, this means the private key content goes into `password` field which is semantically wrong and could cause issues with key parsing.

**2.3. Redis Connection Has No Password**

`credential_store.py` line 194:
```python
self._redis = redis.Redis(
    host=self._redis_host,
    port=self._redis_port,
    decode_responses=True,
)
```

If Redis requires authentication (which it should for credential storage), this will fail silently or allow unauthorized access.

**Recommendation:** Add password support:
```python
redis_password = os.environ.get("REDIS_PASSWORD")
self._redis = redis.Redis(
    host=self._redis_host,
    port=self._redis_port,
    password=redis_password,
    decode_responses=True,
)
```

#### Minor Issues

**2.4. No TTL on Stored Credentials**

Credentials are stored indefinitely with no expiration. Consider adding `await r.expire(credential_key, ttl_seconds)` for compliance with security policies.

**2.5. No Duplicate Name Check**

`save_credential` allows saving multiple credentials with the same name for the same user. Consider enforcing unique names per user.

---

## 3. RBAC Permission Extension

### Status: APPROVED (Minor Issues)

#### Analysis

The RBAC system is well-structured with proper permission hierarchy and inheritance. The `PermissionChecker` class properly implements Org -> Team -> User permission flow.

#### Important Issues

**3.1. Dataset Permissions Not in ROLE_PERMISSIONS Mapping**

`rbac.py` lines 74-85 define role permissions:
```python
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [Permission.TASK_READ],
    Role.DEVELOPER: [Permission.TASK_READ, Permission.TASK_CREATE, Permission.TASK_DELETE],
    Role.ADMIN: [Permission.TASK_READ, Permission.TASK_CREATE, Permission.TASK_DELETE,
                 Permission.ADMIN_USER, Permission.ADMIN_QUOTA, Permission.ADMIN_ALERT],
}
```

Dataset permissions (DATASET_READ, DATASET_CREATE, etc.) are NOT included. A developer cannot create datasets despite the API allowing it.

**Recommendation:** Add dataset permissions to roles:
```python
ROLE_PERMISSIONS: dict[Role, list[Permission]] = {
    Role.VIEWER: [Permission.TASK_READ, Permission.DATASET_READ, Permission.DEPLOY_READ],
    Role.DEVELOPER: [Permission.TASK_READ, Permission.TASK_CREATE, Permission.TASK_DELETE,
                     Permission.DATASET_READ, Permission.DATASET_CREATE, Permission.DATASET_WRITE,
                     Permission.DEPLOY_READ, Permission.DEPLOY_WRITE],
    Role.ADMIN: [Permission.TASK_READ, Permission.TASK_CREATE, Permission.TASK_DELETE,
                 Permission.ADMIN_USER, Permission.ADMIN_QUOTA, Permission.ADMIN_ALERT,
                 Permission.DATASET_READ, Permission.DATASET_CREATE, Permission.DATASET_WRITE,
                 Permission.DATASET_DELETE, Permission.DATASET_ADMIN,
                 Permission.DEPLOY_READ, Permission.DEPLOY_WRITE],
}
```

**3.2. Missing GET /api/datasets/{id}/access Permission Mapping**

`_get_required_permissions()` at line 284 doesn't handle dataset access management routes. The `DATASET_ADMIN` permission is defined but not mapped to any route.

**3.3. Team-based Dataset Access Not Checked**

`check_dataset_access()` in `datasets.py` lines 66-113 and `_check_dataset_access()` in `permission_checker.py` check user_id and explicit access, but do NOT check if user is a member of `dataset.team_id`. Datasets assigned to a team are not accessible to team members.

**Recommendation:** Add team membership check:
```python
# After checking owner
if dataset.team_id:
    # Check if user is a member of the team
    user_teams = self._get_user_team_ids(self.user.user_id)
    if dataset.team_id in user_teams:
        return True  # Team members have read access at minimum
```

---

## Required Fixes Before Production

### Critical (Must Fix)

1. Add `require_permission(Permission.DATASET_READ)` dependency to dataset endpoints
2. Filter `list_datasets` to only show accessible datasets
3. Add encryption key validation in CredentialStore (fail fast if missing)
4. Add Redis password support to CredentialStore

### Important (Should Fix)

5. Escape SQL wildcards in search filter
6. Add dataset permissions to ROLE_PERMISSIONS mapping
7. Prevent non-owner from changing ownership
8. Add team membership check for dataset access

### Minor (Nice to Have)

9. Add TTL to stored credentials
10. Enforce unique credential names per user
11. Handle SSH key credential type properly

---

## Test Coverage Assessment

No tests found for:
- `permission_checker.py` - No unit tests
- `credential_store.py` - No unit tests
- `datasets.py` - No API tests

**Recommendation:** Add test coverage for security-critical components before deployment.

---

## Commit Reference

Phase 3.5 commits: f5baca6, dcd95d7, 9ef71d9, 883d147, e29b71d, 9d7b71b, c43ba73, e5a5356, a66aa18, 8672b67, ed3ec93
