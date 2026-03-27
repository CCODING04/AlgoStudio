# src/algo_studio/api/pagination.py
"""Cursor-based pagination utilities for API endpoints.

This module provides cursor pagination to replace offset/limit pagination,
which is inefficient for large datasets. Cursor pagination uses a stable
sorting key (typically created_at or id) and a cursor to paginate through
results.

Advantages of cursor pagination:
- Consistent results even when data is inserted/deleted during pagination
- O(1) performance vs O(n) for offset pagination
- Better for infinite scroll use cases
"""

import base64
import json
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class CursorParams(BaseModel):
    """Parameters for cursor-based pagination.

    Usage:
        @router.get("/items")
        async def list_items(
            cursor: str | None = None,
            limit: int = 20,
        ):
            params = CursorParams(cursor=cursor, limit=limit)
            items, next_cursor = await fetch_items(params)
            return PaginatedResponse(items=items, next_cursor=next_cursor)
    """

    cursor: str | None = Field(default=None, description="Pagination cursor (base64 encoded)")
    limit: int = Field(default=20, ge=1, le=100, description="Number of items per page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Response model for paginated results.

    Attributes:
        items: List of items for the current page
        next_cursor: Cursor for the next page (None if no more pages)
        total: Total count of items (optional, expensive to compute)
        has_more: Whether there are more pages (alternative to next_cursor)
    """

    items: list[T]
    next_cursor: str | None = Field(default=None, description="Cursor for next page")
    total: int | None = Field(default=None, description="Total count of items")
    has_more: bool = Field(default=False, description="Whether more pages exist")


class Cursor:
    """Cursor for pagination containing sort key value and position.

    The cursor encodes the sort key value and optional additional
    filters to ensure consistent pagination.

    Attributes:
        sort_value: The value to resume pagination from
        id: Optional secondary sort key (for tie-breaking)
        created_at: Timestamp for created_at based cursors
    """

    def __init__(
        self,
        sort_value: Any,
        id: str | None = None,
        created_at: datetime | None = None,
    ):
        self.sort_value = sort_value
        self.id = id
        self.created_at = created_at

    def encode(self) -> str:
        """Encode cursor to base64 string.

        Returns:
            Base64 encoded cursor string
        """
        data = {
            "v": self.sort_value,
        }
        if self.id is not None:
            data["id"] = self.id
        if self.created_at is not None:
            data["ts"] = self.created_at.isoformat()

        json_str = json.dumps(data, default=str)
        return base64.urlsafe_b64encode(json_str.encode()).decode()

    @classmethod
    def decode(cls, cursor_str: str) -> "Cursor":
        """Decode cursor from base64 string.

        Args:
            cursor_str: Base64 encoded cursor string

        Returns:
            Decoded Cursor object

        Raises:
            ValueError: If cursor is invalid or cannot be decoded
        """
        try:
            json_str = base64.urlsafe_b64decode(cursor_str.encode()).decode()
            data = json.loads(json_str)

            return cls(
                sort_value=data["v"],
                id=data.get("id"),
                created_at=datetime.fromisoformat(data["ts"]) if "ts" in data else None,
            )
        except Exception as e:
            raise ValueError(f"Invalid cursor: {cursor_str}") from e


def encode_cursor(sort_value: Any, id: str | None = None) -> str:
    """Convenience function to encode a cursor.

    Args:
        sort_value: The sort key value (e.g., datetime, int, string)
        id: Optional secondary sort key for tie-breaking

    Returns:
        Base64 encoded cursor string
    """
    cursor = Cursor(sort_value=sort_value, id=id)
    return cursor.encode()


def decode_cursor(cursor_str: str) -> Cursor:
    """Convenience function to decode a cursor.

    Args:
        cursor_str: Base64 encoded cursor string

    Returns:
        Decoded Cursor object

    Raises:
        ValueError: If cursor is invalid
    """
    return Cursor.decode(cursor_str)


def make_paginated_response(
    items: list[T],
    next_sort_value: Any | None,
    next_id: str | None = None,
    total: int | None = None,
) -> PaginatedResponse[T]:
    """Create a paginated response with next cursor.

    Args:
        items: List of items for current page
        next_sort_value: Sort value for next page (None if last page)
        next_id: Optional secondary sort key for next page
        total: Optional total count

    Returns:
        PaginatedResponse with items and next_cursor
    """
    has_more = next_sort_value is not None
    next_cursor = None

    if has_more:
        next_cursor = encode_cursor(next_sort_value, next_id)

    return PaginatedResponse(
        items=items,
        next_cursor=next_cursor,
        total=total,
        has_more=has_more,
    )


class CursorPage:
    """Helper for building paginated queries.

    This class helps build SQLAlchemy queries with cursor pagination.

    Usage:
        page = CursorPage(
            sort_column=Task.created_at,
            cursor=cursor_str,  # Optional
            limit=20,
        )

        query = page.apply(Task.__table__)
        results = await session.execute(query)
    """

    def __init__(
        self,
        sort_column: Any,
        cursor: str | None = None,
        limit: int = 20,
        id_column: Any = None,
    ):
        """Initialize cursor page helper.

        Args:
            sort_column: Column to sort by (e.g., Task.created_at)
            cursor: Optional cursor string to resume from
            limit: Number of items per page
            id_column: Optional secondary sort column for tie-breaking
        """
        self.sort_column = sort_column
        self.id_column = id_column
        self.cursor = cursor
        self.limit = limit
        self._cursor_value: Any = None
        self._cursor_id: Any = None

        if cursor:
            try:
                decoded = decode_cursor(cursor)
                self._cursor_value = decoded.sort_value
                self._cursor_id = decoded.id
            except ValueError:
                pass  # Invalid cursor, start from beginning

    @property
    def has_cursor(self) -> bool:
        """Check if a valid cursor is set."""
        return self._cursor_value is not None

    def get_filter(self):
        """Get SQLAlchemy filter for cursor pagination.

        Returns:
            SQLAlchemy filter condition or None
        """
        from sqlalchemy import and_, or_

        if not self.has_cursor:
            return None

        if self.id_column and self._cursor_id:
            # Complex filter with tie-breaking on secondary column
            # (sort_col, id) > (cursor_val, cursor_id)
            return or_(
                self.sort_column < self._cursor_value,
                and_(
                    self.sort_column == self._cursor_value,
                    self.id_column < self._cursor_id,
                ),
            )
        else:
            # Simple filter on primary sort column
            return self.sort_column < self._cursor_value
