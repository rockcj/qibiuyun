"""后端测试公共 fixture：内存数据库、HTTP 客户端、演示用户。"""

import os
import sys
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# 将 backend 目录加入 Python 路径
BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# 测试环境使用内存 SQLite，避免污染开发数据库
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/1")
os.environ.setdefault("LLM_API_KEY", "")
os.environ.setdefault("DEEPSEEK_API_KEY", "")

from models.base import Base, User  # noqa: E402


@pytest_asyncio.fixture
async def test_engine():
    """创建测试用内存数据库引擎。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine):
    """提供带演示用户的异步数据库会话。"""
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        demo_user = User(email="demo@offergpt.local", name="Test User", plan="free")
        session.add(demo_user)
        await session.commit()
        yield session


@pytest_asyncio.fixture
async def app_client(test_engine, monkeypatch):
    """
    提供 FastAPI 异步测试客户端。
    覆盖 get_db 依赖和 init_db，使用内存数据库。
    """
    factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # 延迟导入，确保环境变量已生效
    import database as db_module
    from main import app

    # 种子演示用户
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == "demo@offergpt.local"))
        if result.scalar_one_or_none() is None:
            session.add(User(email="demo@offergpt.local", name="Demo User", plan="free"))
            await session.commit()

    monkeypatch.setattr(db_module, "async_session_factory", factory)
    app.dependency_overrides[db_module.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture
def sample_resume_text() -> str:
    """标准测试简历文本。"""
    return (
        "John Doe - Software Engineer\n"
        "Skills: Python, FastAPI, React, LLM, RAG, PostgreSQL\n"
        "Project: AI Interview System - Backend Developer - Reduced latency by 35%\n"
        "Experience: 3 years building AI applications with measurable 40% improvement"
    )


@pytest.fixture
def sample_jd_payload() -> dict:
    """标准测试 JD 请求体。"""
    return {
        "title": "AI Application Engineer",
        "company": "Demo Company",
        "jdText": (
            "We are looking for a senior engineer with LLM application experience, "
            "Python, RAG, API Design and system design skills. "
            "Strong problem solving and communication required."
        ),
    }
