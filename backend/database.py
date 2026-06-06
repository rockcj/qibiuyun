"""Database engine and session factory with SQLAlchemy async support."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy import text
from config import settings


def _resolve_url(raw: str) -> str:
    """Auto-add async driver: postgresql:// → postgresql+asyncpg://"""
    if "+" in raw.split("://")[0]:
        return raw
    if raw.startswith("postgresql://"):
        return raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    if raw.startswith("sqlite:///"):
        return raw.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    return raw


_db_url = _resolve_url(settings.database_url)
_echo = settings.is_development

_engine_kwargs = dict(echo=_echo)
if "sqlite" not in _db_url:
    _engine_kwargs.update(pool_size=10, max_overflow=20)

engine = create_async_engine(_db_url, **_engine_kwargs)

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


# Seeded demo user ID (populated by init_db)
DEMO_USER_ID = None


async def init_db():
    """Create all tables and seed demo data on startup."""
    from models.base import Base, User
    from sqlalchemy import select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 迁移：为已有 users 表补充 hashed_password 列（避免 ALTER 失败阻塞启动）
        try:
            await conn.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS hashed_password VARCHAR(255)")
            )
        except Exception:
            pass  # SQLite 等不支持 IF NOT EXISTS，忽略

    # Seed demo user for MVP
    global DEMO_USER_ID
    async with async_session_factory() as session:
        result = await session.execute(
            select(User).where(User.email == "demo@offergpt.local")
        )
        demo_user = result.scalar_one_or_none()
        if demo_user is None:
            demo_user = User(
                email="demo@offergpt.local",
                name="Demo User",
                plan="free",
            )
            session.add(demo_user)
            await session.commit()
            print(f"[OfferGPT] Demo user created: {demo_user.id}")
        else:
            print(f"[OfferGPT] Demo user exists: {demo_user.id}")
        DEMO_USER_ID = demo_user.id
