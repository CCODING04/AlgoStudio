# tests/integration/test_database_integration.py
"""Integration tests for Database module.

These tests verify the DatabaseManager and model operations.
"""

import pytest
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy import select


class TestDatabaseManager:
    """Test suite for DatabaseManager integration."""

    @pytest.fixture
    async def db_manager(self):
        """Provide a test database manager with in-memory SQLite."""
        from algo_studio.db.session import DatabaseManager

        manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
        manager.init()
        await manager.create_tables()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_database_manager_init(self):
        """Test database manager initialization."""
        from algo_studio.db.session import DatabaseManager

        manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
        manager.init()

        assert manager._engine is not None
        assert manager._session_factory is not None
        await manager.close()

    @pytest.mark.asyncio
    async def test_create_and_drop_tables(self, db_manager):
        """Test creating and dropping tables."""
        # Tables should exist after create_tables
        await db_manager.drop_tables()
        await db_manager.create_tables()

        # If we get here without error, the test passes

    @pytest.mark.asyncio
    async def test_session_context_manager(self, db_manager):
        """Test database session context manager."""
        async with db_manager.session() as session:
            # Should be able to execute queries
            from sqlalchemy import text
            result = await session.execute(text("SELECT 1"))
            row = result.scalar()
            assert row == 1

    @pytest.mark.asyncio
    async def test_session_commit(self, db_manager):
        """Test that session commits on success."""
        async with db_manager.session() as session:
            from sqlalchemy import text
            await session.execute(text("CREATE TABLE IF NOT EXISTS test (id INTEGER)"))
            await session.execute(text("INSERT INTO test VALUES (1)"))

    @pytest.mark.asyncio
    async def test_session_rollback_on_error(self, db_manager):
        """Test that session rolls back on error."""
        with pytest.raises(Exception):
            async with db_manager.session() as session:
                from sqlalchemy import text
                await session.execute(text("INVALID SQL"))
                await session.commit()


class TestTaskModelDatabase:
    """Test suite for Task model database operations."""

    @pytest.fixture
    async def db_manager(self):
        """Provide a test database manager."""
        from algo_studio.db.session import DatabaseManager

        manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
        manager.init()
        await manager.create_tables()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_create_task_record(self, db_manager):
        """Test creating a Task record in the database."""
        from algo_studio.db.models.task import Task
        from sqlalchemy import select

        task = Task(
            task_id="test-task-001",
            task_type="train",
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status="pending",
            config={"epochs": 100},
        )

        async with db_manager.session() as session:
            session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(select(Task).where(Task.task_id == "test-task-001"))
            fetched_task = result.scalar_one_or_none()

        assert fetched_task is not None
        assert fetched_task.task_id == "test-task-001"
        assert fetched_task.task_type == "train"
        assert fetched_task.status == "pending"

    @pytest.mark.asyncio
    async def test_update_task_status(self, db_manager):
        """Test updating task status in database."""
        from algo_studio.db.models.task import Task

        task = Task(
            task_id="test-task-002",
            task_type="train",
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status="pending",
        )

        async with db_manager.session() as session:
            session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-002")
            )
            fetched_task = result.scalar_one_or_none()
            fetched_task.status = "running"
            fetched_task.started_at = datetime.now()
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-002")
            )
            updated_task = result.scalar_one_or_none()

        assert updated_task.status == "running"
        assert updated_task.started_at is not None

    @pytest.mark.asyncio
    async def test_task_with_result(self, db_manager):
        """Test storing task result in database."""
        from algo_studio.db.models.task import Task

        task = Task(
            task_id="test-task-003",
            task_type="train",
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status="completed",
            result={"accuracy": 0.95, "loss": 0.05},
        )

        async with db_manager.session() as session:
            session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-003")
            )
            fetched_task = result.scalar_one_or_none()

        assert fetched_task.result is not None
        assert fetched_task.result["accuracy"] == 0.95

    @pytest.mark.asyncio
    async def test_task_with_error(self, db_manager):
        """Test storing task error in database."""
        from algo_studio.db.models.task import Task

        task = Task(
            task_id="test-task-004",
            task_type="train",
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status="failed",
            error="GPU memory exceeded",
        )

        async with db_manager.session() as session:
            session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-004")
            )
            fetched_task = result.scalar_one_or_none()

        assert fetched_task.status == "failed"
        assert fetched_task.error == "GPU memory exceeded"

    @pytest.mark.asyncio
    async def test_task_progress_tracking(self, db_manager):
        """Test task progress tracking in database."""
        from algo_studio.db.models.task import Task

        task = Task(
            task_id="test-task-005",
            task_type="train",
            algorithm_name="simple_classifier",
            algorithm_version="v1",
            status="running",
            progress=0,
        )

        async with db_manager.session() as session:
            session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-005")
            )
            fetched_task = result.scalar_one_or_none()
            fetched_task.progress = 50
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == "test-task-005")
            )
            updated_task = result.scalar_one_or_none()

        assert updated_task.progress == 50

    @pytest.mark.asyncio
    async def test_task_list_query(self, db_manager):
        """Test querying multiple tasks."""
        from algo_studio.db.models.task import Task
        from sqlalchemy import select, func

        tasks = [
            Task(task_id="test-task-006", task_type="train", algorithm_name="a", algorithm_version="v1", status="completed"),
            Task(task_id="test-task-007", task_type="train", algorithm_name="b", algorithm_version="v1", status="running"),
            Task(task_id="test-task-008", task_type="infer", algorithm_name="a", algorithm_version="v1", status="pending"),
        ]

        async with db_manager.session() as session:
            for task in tasks:
                session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(select(func.count()).select_from(Task))
            count = result.scalar()

        assert count == 3

    @pytest.mark.asyncio
    async def test_task_filter_by_status(self, db_manager):
        """Test filtering tasks by status."""
        from algo_studio.db.models.task import Task
        from sqlalchemy import select

        tasks = [
            Task(task_id="test-task-009", task_type="train", algorithm_name="a", algorithm_version="v1", status="completed"),
            Task(task_id="test-task-010", task_type="train", algorithm_name="b", algorithm_version="v1", status="running"),
        ]

        async with db_manager.session() as session:
            for task in tasks:
                session.add(task)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(
                select(Task).where(Task.status == "completed")
            )
            completed_tasks = result.scalars().all()

        assert len(completed_tasks) == 1
        assert completed_tasks[0].task_id == "test-task-009"


class TestUserModelDatabase:
    """Test suite for User model database operations."""

    @pytest.fixture
    async def db_manager(self):
        """Provide a test database manager."""
        from algo_studio.db.session import DatabaseManager

        manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
        manager.init()
        await manager.create_tables()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_create_user_record(self, db_manager):
        """Test creating a User record in the database."""
        from algo_studio.db.models.user import User
        from sqlalchemy import select

        user = User(
            user_id="user-001",
            username="testuser",
            email="test@example.com",
        )

        async with db_manager.session() as session:
            session.add(user)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(select(User).where(User.user_id == "user-001"))
            fetched_user = result.scalar_one_or_none()

        assert fetched_user is not None
        assert fetched_user.username == "testuser"
        assert fetched_user.email == "test@example.com"


class TestQuotaModelDatabase:
    """Test suite for Quota model database operations."""

    @pytest.fixture
    async def db_manager(self):
        """Provide a test database manager."""
        from algo_studio.db.session import DatabaseManager

        manager = DatabaseManager(db_url="sqlite+aiosqlite:///:memory:")
        manager.init()
        await manager.create_tables()
        yield manager
        await manager.close()

    @pytest.mark.asyncio
    async def test_create_quota_record(self, db_manager):
        """Test creating a Quota record in the database."""
        from algo_studio.db.models.quota import Quota

        quota = Quota(
            quota_id="quota-001",
            scope="user",
            scope_id="user-001",
            name="User GPU Quota",
            gpu_count=1,
            gpu_memory_gb=24.0,
            memory_gb=32.0,
            concurrent_tasks=2,
        )

        async with db_manager.session() as session:
            session.add(quota)
            await session.commit()

        async with db_manager.session() as session:
            result = await session.execute(select(Quota).where(Quota.quota_id == "quota-001"))
            fetched_quota = result.scalar_one_or_none()

        assert fetched_quota is not None
        assert fetched_quota.scope == "user"
        assert fetched_quota.scope_id == "user-001"
        assert fetched_quota.gpu_count == 1
        assert fetched_quota.gpu_memory_gb == 24.0
