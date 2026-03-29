# src/algo_studio/api/routes/datasets.py
"""Dataset API routes for CRUD operations."""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from algo_studio.api.dataset_models import (
    DatasetCreateRequest,
    DatasetUpdateRequest,
    DatasetResponse,
    DatasetListResponse,
    DatasetAccessRequest,
    DatasetAccessResponse,
    DatasetUploadRequest,
    DatasetUploadResponse,
)
from algo_studio.api.middleware.rbac import Permission
from algo_studio.db.models.dataset import Dataset, DatasetAccess
from algo_studio.db.models.user import User
from algo_studio.db.session import get_session

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


def _dataset_to_response(dataset: Dataset) -> DatasetResponse:
    """Convert Dataset model to response."""
    return DatasetResponse(
        dataset_id=dataset.dataset_id,
        name=dataset.name,
        description=dataset.description,
        path=dataset.path,
        storage_type=dataset.storage_type,
        size_gb=dataset.size_gb,
        file_count=dataset.file_count,
        version=dataset.version,
        extra_metadata=dataset.extra_metadata,
        tags=dataset.tags,
        is_public=dataset.is_public,
        owner_id=dataset.owner_id,
        team_id=dataset.team_id,
        is_active=dataset.is_active,
        last_accessed_at=dataset.last_accessed_at,
        created_at=dataset.created_at,
        updated_at=dataset.updated_at,
    )


def _access_to_response(access: DatasetAccess) -> DatasetAccessResponse:
    """Convert DatasetAccess model to response."""
    return DatasetAccessResponse(
        id=access.id,
        dataset_id=access.dataset_id,
        user_id=access.user_id,
        team_id=access.team_id,
        access_level=access.access_level,
        granted_at=access.granted_at,
        granted_by=access.granted_by,
    )


async def check_dataset_access(
    session: AsyncSession,
    user: User,
    dataset_id: str,
    required_level: str,
) -> bool:
    """Check if user has required access level to dataset.

    Allows access if:
    - User is superuser
    - Dataset is public and required_level is 'read'
    - User is the dataset owner
    - User has explicit access in dataset_access table
    """
    # Get dataset
    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        return False

    # Superuser has all permissions
    if user.is_superuser:
        return True

    # Public datasets - anyone can read
    if dataset.is_public and required_level == "read":
        return True

    # Owner has all permissions
    if dataset.owner_id == user.user_id:
        return True

    # Check dataset_access table
    result = await session.execute(
        select(DatasetAccess).where(
            DatasetAccess.dataset_id == dataset_id,
            DatasetAccess.user_id == user.user_id
        )
    )
    access = result.scalar_one_or_none()

    if not access:
        return False

    level_hierarchy = {"read": 0, "write": 1, "admin": 2}
    return level_hierarchy.get(access.access_level, -1) >= level_hierarchy.get(required_level, 99)


@router.post("", response_model=DatasetResponse)
async def create_dataset(
    request: DatasetCreateRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Create a new dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Check if dataset name already exists
    result = await session.execute(
        select(Dataset).where(Dataset.name == request.name)
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Dataset with name '{request.name}' already exists")

    # Create dataset
    dataset = Dataset(
        dataset_id=f"ds-{uuid.uuid4().hex[:12]}",
        name=request.name,
        description=request.description,
        path=request.path,
        storage_type=request.storage_type,
        extra_metadata=request.extra_metadata,
        tags=request.tags,
        is_public=request.is_public,
        owner_id=user.user_id,
        team_id=request.team_id,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)

    return _dataset_to_response(dataset)


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    req: Request,
    session: AsyncSession = Depends(get_session),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    search: Optional[str] = Query(default=None, description="Search by name"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
):
    """List all datasets with pagination."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Build query
    query = select(Dataset)

    # Apply filters
    if search:
        query = query.where(Dataset.name.ilike(f"%{search}%"))
    if is_active is not None:
        query = query.where(Dataset.is_active == is_active)
    else:
        # By default, only show active datasets
        query = query.where(Dataset.is_active == True)

    # Get total count
    count_query = select(func.count()).select_from(Dataset)
    if search:
        count_query = count_query.where(Dataset.name.ilike(f"%{search}%"))
    if is_active is not None:
        count_query = count_query.where(Dataset.is_active == is_active)
    else:
        count_query = count_query.where(Dataset.is_active == True)

    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Dataset.created_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    datasets = result.scalars().all()

    return DatasetListResponse(
        items=[_dataset_to_response(ds) for ds in datasets],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + len(datasets)) < total,
    )


@router.get("/{dataset_id}", response_model=DatasetResponse)
async def get_dataset(
    dataset_id: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Get a specific dataset by ID."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Update last accessed time
    dataset.last_accessed_at = datetime.utcnow()
    await session.commit()

    return _dataset_to_response(dataset)


@router.put("/{dataset_id}", response_model=DatasetResponse)
async def update_dataset(
    dataset_id: str,
    request: DatasetUpdateRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Update a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check write permission
    if not await check_dataset_access(session, user, dataset_id, "write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Update fields
    if request.name is not None:
        # Check if name is already taken
        result = await session.execute(
            select(Dataset).where(
                Dataset.name == request.name,
                Dataset.dataset_id != dataset_id
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"Dataset name '{request.name}' already exists")
        dataset.name = request.name

    if request.description is not None:
        dataset.description = request.description
    if request.extra_metadata is not None:
        dataset.extra_metadata = request.extra_metadata
    if request.tags is not None:
        dataset.tags = request.tags
    if request.is_public is not None:
        dataset.is_public = request.is_public

    await session.commit()
    await session.refresh(dataset)

    return _dataset_to_response(dataset)


@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Soft delete a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check delete permission (same as write)
    if not await check_dataset_access(session, user, dataset_id, "write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Soft delete
    dataset.is_active = False
    await session.commit()

    return {"message": "Dataset deleted successfully", "dataset_id": dataset_id}


@router.post("/{dataset_id}/restore", response_model=DatasetResponse)
async def restore_dataset(
    dataset_id: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Restore a soft-deleted dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Only admin or owner can restore
    if not user.is_superuser and dataset.owner_id != user.user_id:
        raise HTTPException(status_code=403, detail="Only owner or admin can restore dataset")

    dataset.is_active = True
    await session.commit()
    await session.refresh(dataset)

    return _dataset_to_response(dataset)


@router.post("/{dataset_id}/upload", response_model=DatasetUploadResponse)
async def initiate_upload(
    dataset_id: str,
    request: DatasetUploadRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Initiate a dataset upload (for files < 5GB)."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Check file size limit (5GB)
    max_size_bytes = 5 * 1024 * 1024 * 1024
    if request.size_bytes > max_size_bytes:
        raise HTTPException(status_code=400, detail="File size exceeds 5GB limit")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check write permission
    if not await check_dataset_access(session, user, dataset_id, "write"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Generate upload ID and simulate upload URL
    upload_id = f"upload-{uuid.uuid4().hex[:16]}"
    expires_at = datetime.utcnow()

    return DatasetUploadResponse(
        upload_id=upload_id,
        upload_url=f"/api/datasets/{dataset_id}/upload/{upload_id}",
        expires_at=expires_at,
    )


# Access control endpoints

@router.get("/{dataset_id}/access", response_model=list[DatasetAccessResponse])
async def list_dataset_access(
    dataset_id: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """List all access permissions for a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check admin permission
    if not await check_dataset_access(session, user, dataset_id, "admin"):
        raise HTTPException(status_code=403, detail="Permission denied")

    result = await session.execute(
        select(DatasetAccess).where(DatasetAccess.dataset_id == dataset_id)
    )
    access_list = result.scalars().all()

    return [_access_to_response(access) for access in access_list]


@router.post("/{dataset_id}/access", response_model=DatasetAccessResponse)
async def grant_dataset_access(
    dataset_id: str,
    request: DatasetAccessRequest,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Grant access to a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check admin permission
    if not await check_dataset_access(session, user, dataset_id, "admin"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Validate that at least one of user_id or team_id is provided
    if not request.user_id and not request.team_id:
        raise HTTPException(status_code=400, detail="Either user_id or team_id must be provided")

    # Create access record
    access = DatasetAccess(
        dataset_id=dataset_id,
        user_id=request.user_id,
        team_id=request.team_id,
        access_level=request.access_level,
        granted_by=user.user_id,
    )
    session.add(access)
    await session.commit()
    await session.refresh(access)

    return _access_to_response(access)


@router.delete("/{dataset_id}/access/{access_id}")
async def revoke_dataset_access(
    dataset_id: str,
    access_id: int,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """Revoke access to a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(DatasetAccess).where(
            DatasetAccess.id == access_id,
            DatasetAccess.dataset_id == dataset_id
        )
    )
    access = result.scalar_one_or_none()
    if not access:
        raise HTTPException(status_code=404, detail="Access record not found")

    # Check admin permission
    if not await check_dataset_access(session, user, dataset_id, "admin"):
        raise HTTPException(status_code=403, detail="Permission denied")

    await session.delete(access)
    await session.commit()

    return {"message": "Access revoked successfully"}


@router.get("/{dataset_id}/tasks")
async def list_dataset_tasks(
    dataset_id: str,
    req: Request,
    session: AsyncSession = Depends(get_session),
):
    """List all tasks associated with a dataset."""
    user: Optional[User] = getattr(req.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    result = await session.execute(
        select(Dataset).where(Dataset.dataset_id == dataset_id)
    )
    dataset = result.scalar_one_or_none()
    if not dataset:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")

    # Check read permission
    if not await check_dataset_access(session, user, dataset_id, "read"):
        raise HTTPException(status_code=403, detail="Permission denied")

    # Return empty list - tasks are accessed via the relationship
    return []
