# src/algo_studio/db/session.py
"""Database session management for async SQLite with WAL mode."""

import threading
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from algo_studio.db.models.base import Base


class DatabaseManager:
    """Manages database connections and sessions with WAL mode.

    Uses thread-local connections for SQLite with WAL mode enabled.
    """

    def __init__(self, db_url: str = "sqlite+aiosqlite:///./algo_studio.db"):
        """Initialize database manager.

        Args:
            db_url: SQLAlchemy database URL
        """
        self.db_url = db_url
        self._engine = None
        self._session_factory = None
        self._local = threading.local()

    def init(self):
        """Initialize the database engine and session factory."""
        self._engine = create_async_engine(
            self.db_url,
            echo=False,
            poolclass=None,  # Use NullPool for SQLite WAL mode
        )

        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )

    async def close(self):
        """Close the database engine."""
        if self._engine:
            await self._engine.dispose()

    @contextmanager
    def _get_conn(self):
        """Get a synchronous connection for event listeners."""
        if self._engine is None:
            self.init()
        conn = self._engine.sync_engine.connect()
        try:
            yield conn
        finally:
            conn.close()

    def _set_wal_mode(self, conn):
        """Enable WAL mode on a connection."""
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA busy_timeout=30000"))
        conn.commit()

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get an async database session.

        Usage:
            async with db.session() as session:
                result = await session.execute(...)
        """
        if self._session_factory is None:
            self.init()

        # Enable WAL mode for this connection
        session = self._session_factory()
        try:
            # Execute PRAGMA commands to set WAL mode
            await session.execute(text("PRAGMA journal_mode=WAL"))
            await session.execute(text("PRAGMA busy_timeout=30000"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def session_scope(self, **kwargs) -> AsyncGenerator[AsyncSession, None]:
        """Get an async session with specific transaction behavior.

        Args:
            **kwargs: Additional arguments to sessionmaker

        Usage:
            async with db.session_scope() as session:
                result = await session.execute(...)
        """
        if self._session_factory is None:
            self.init()

        session = self._session_factory(**kwargs)
        try:
            await session.execute(text("PRAGMA journal_mode=WAL"))
            await session.execute(text("PRAGMA busy_timeout=30000"))
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    async def create_tables(self):
        """Create all tables defined in models."""
        if self._engine is None:
            self.init()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Drop all tables defined in models."""
        if self._engine is None:
            self.init()

        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


# Global database manager instance
db = DatabaseManager()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for getting database sessions.

    Usage:
        @app.get("/items")
        async def get_items(session: AsyncSession = Depends(get_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    async with db.session() as session:
        yield session
