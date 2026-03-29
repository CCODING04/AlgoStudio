# src/algo_studio/api/models/dataset.py
"""Pydantic models for Dataset API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasetCreateRequest(BaseModel):
    """Request model for creating a dataset."""
    name: str = Field(..., min_length=1, max_length=255, description="Dataset name (unique)")
    description: Optional[str] = Field(None, description="Dataset description")
    path: str = Field(..., description="Dataset path on NAS")
    storage_type: str = Field(default="dvc", pattern="^(dvc|nas|raw)$", description="Storage type")
    extra_metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    tags: Optional[List[str]] = Field(None, description="Dataset tags")
    is_public: bool = Field(default=False, description="Whether dataset is publicly accessible")
    team_id: Optional[str] = Field(None, description="Owner team ID")


class DatasetUpdateRequest(BaseModel):
    """Request model for updating a dataset."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    extra_metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    is_public: Optional[bool] = None


class DatasetResponse(BaseModel):
    """Response model for a dataset."""
    dataset_id: str
    name: str
    description: Optional[str]
    path: str
    storage_type: str
    size_gb: Optional[float]
    file_count: Optional[int]
    version: Optional[str]
    extra_metadata: Optional[Dict[str, Any]]
    tags: Optional[List[str]]
    is_public: bool
    owner_id: Optional[str]
    team_id: Optional[str]
    is_active: bool
    last_accessed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class DatasetListResponse(BaseModel):
    """Response model for listing datasets."""
    items: List[DatasetResponse]
    total: int
    page: int
    page_size: int
    has_more: bool


class DatasetAccessRequest(BaseModel):
    """Request model for granting dataset access."""
    user_id: Optional[str] = None
    team_id: Optional[str] = None
    access_level: str = Field(default="read", pattern="^(read|write|admin)$")


class DatasetAccessResponse(BaseModel):
    """Response model for dataset access record."""
    id: int
    dataset_id: str
    user_id: Optional[str]
    team_id: Optional[str]
    access_level: str
    granted_at: datetime
    granted_by: Optional[str]

    class Config:
        from_attributes = True


class DatasetUploadRequest(BaseModel):
    """Request model for initiating dataset upload."""
    filename: str = Field(..., description="Original filename")
    size_bytes: int = Field(..., description="File size in bytes")
    storage_type: str = Field(default="nas", pattern="^(nas|dvc)$", description="Storage destination")


class DatasetUploadResponse(BaseModel):
    """Response model for upload initiation."""
    upload_id: str
    upload_url: str
    expires_at: datetime
