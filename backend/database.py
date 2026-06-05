"""Database engine and session factory with SQLAlchemy async support."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from config import settings

# SQLite only supports NullPool; PostgreSQL / others use QueuePool
_engine_kwargs = dict(echo=settings.env == "development")
if "sqlite" not in settings.database_url:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_async_engine(settings.database_url, **_engine_kwargs)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables on startup."""
    from models.base import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
