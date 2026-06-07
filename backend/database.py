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
    from models.base import Base, User, Interview, TimelineEvent, Report
    from sqlalchemy import select
    import uuid as _uuid

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

        # 预置 Demo 会话数据（用于 /demo 离线路由）
        await _seed_demo_session(session, demo_user.id)


async def _seed_demo_session(session, demo_user_id):
    """预置 demo_interview_001 完整训练会话：transcript + 报告 + VAR 事件。"""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from models.base import Interview, TimelineEvent, Report
    import uuid as _uuid

    DEMO_SESSION_ID = _uuid.UUID("de000001-0000-0000-0000-000000000001")

    # 检查是否已存在
    existing = await session.execute(
        select(Interview).where(Interview.id == DEMO_SESSION_ID)
    )
    if existing.scalar_one_or_none() is not None:
        print("[OfferGPT] Demo session already seeded, skipping")
        return

    # 1) 创建 Interview 记录
    interview = Interview(
        id=DEMO_SESSION_ID,
        user_id=demo_user_id,
        scene="interview",
        topic="Backend Engineer",
        role_mode="friendly_interviewer",
        persona_mode="friendly_interviewer",
        scene_config={
            "scene": "interview",
            "topic": "Backend Engineer",
            "roleMode": "friendly_interviewer",
            "personaMode": "friendly_interviewer",
            "difficultyLevel": "middle",
            "durationMinutes": 15,
            "rubric": ["english", "logic", "confidence", "star", "technical", "communication"],
        },
        status="completed",
        duration_seconds=180,
        transcript={
            "turns": [
                {
                    "turnId": "turn_001", "role": "assistant",
                    "text": "Hello! Welcome to the interview for the Backend Engineer position. Could you start by telling me about your experience with distributed systems?",
                    "startMs": 0, "endMs": 8000,
                },
                {
                    "turnId": "turn_002", "role": "user",
                    "text": "Sure! I have about five years of experience building microservices using Go and Python. At my last company, I designed a message queue system that handled over 10 million events per day.",
                    "startMs": 9000, "endMs": 22000,
                },
                {
                    "turnId": "turn_003", "role": "assistant",
                    "text": "That's impressive! How did you handle failure scenarios in that message queue system?",
                    "startMs": 23000, "endMs": 30000,
                },
                {
                    "turnId": "turn_004", "role": "user",
                    "text": "We implemented a dead letter queue for messages that failed after three retries. Also, we used... um... we used circuit breakers to prevent cascade failures. The system had... uh... 99.9% uptime over two years.",
                    "startMs": 31000, "endMs": 48000,
                },
                {
                    "turnId": "turn_005", "role": "assistant",
                    "text": "Great answer! Let me ask about your experience with database design. How would you model a multi-tenant SaaS application's data layer?",
                    "startMs": 49000, "endMs": 56000,
                },
                {
                    "turnId": "turn_006", "role": "user",
                    "text": "I would use a shared database with tenant ID column for isolation. Each table has a tenant_id foreign key. For high-security tenants, we can use separate schemas. I also designed... I have designed indexing strategies for tenant-scoped queries.",
                    "startMs": 57000, "endMs": 72000,
                },
                {
                    "turnId": "turn_007", "role": "assistant",
                    "text": "Excellent! Now let's discuss system design. How would you design a real-time notification system that can scale to millions of users?",
                    "startMs": 73000, "endMs": 81000,
                },
                {
                    "turnId": "turn_008", "role": "user",
                    "text": "I would use WebSocket connections with a pub-sub model. The notification service publishes events to Kafka, and each user's connection subscribes to their own topic. For offline users, we store notifications in a database and sync when they come back online.",
                    "startMs": 82000, "endMs": 98000,
                },
                {
                    "turnId": "turn_009", "role": "assistant",
                    "text": "That's a well-thought-out design. One final question: can you describe a time when you had to make a difficult technical trade-off?",
                    "startMs": 99000, "endMs": 105000,
                },
                {
                    "turnId": "turn_010", "role": "user",
                    "text": "Yes. We had to choose between consistency and availability for our payment system. We chose eventual consistency with idempotency keys to ensure no double-charging. This allowed us to keep the system available during peak traffic while maintaining data integrity.",
                    "startMs": 106000, "endMs": 122000,
                },
            ],
        },
        metrics_json={
            "corrections": [
                {"turnId": "turn_004", "original": "We implemented a dead letter queue", "corrected": "We implemented a dead letter queue", "severity": "minor", "transcript": "we um used circuit breakers"},
                {"turnId": "turn_006", "original": "I also designed... I have designed indexing strategies", "corrected": "I have also designed indexing strategies", "severity": "minor", "transcript": "I also designed"},
            ],
            "fillerCounts": {"um": 2, "uh": 1},
            "pronunciation": [
                {"turnId": "turn_002", "wordsPerMinute": 135, "pauseCount": 2, "lowConfidenceWords": ["microservices"], "durationSeconds": 13, "wordCount": 29, "overallConfidence": 0.85},
                {"turnId": "turn_004", "wordsPerMinute": 120, "pauseCount": 4, "lowConfidenceWords": ["circuit", "cascade"], "durationSeconds": 17, "wordCount": 34, "overallConfidence": 0.72},
                {"turnId": "turn_006", "wordsPerMinute": 110, "pauseCount": 3, "lowConfidenceWords": ["tenant-scoped"], "durationSeconds": 15, "wordCount": 27, "overallConfidence": 0.78},
                {"turnId": "turn_008", "wordsPerMinute": 140, "pauseCount": 1, "lowConfidenceWords": [], "durationSeconds": 16, "wordCount": 37, "overallConfidence": 0.90},
                {"turnId": "turn_010", "wordsPerMinute": 130, "pauseCount": 2, "lowConfidenceWords": ["idempotency"], "durationSeconds": 16, "wordCount": 35, "overallConfidence": 0.82},
            ],
        },
        started_at=datetime(2026, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 6, 1, 10, 3, 0, tzinfo=timezone.utc),
    )
    session.add(interview)
    await session.flush()

    # 2) 创建 TimelineEvent（VAR 事件）
    timeline_events = [
        TimelineEvent(
            interview_id=DEMO_SESSION_ID,
            turn_id="turn_002",
            event_type="pronunciation",
            severity="low",
            title="发音纠正：microservices",
            description="单词 'microservices' 发音置信度较低，建议拆分音节练习：mi-cro-ser-vi-ces",
            start_ms=12000, end_ms=14000,
            transcript_snippet="I have about five years of experience building microservices using Go and Python.",
            evidence={"confidence": 0.65, "word": "microservices"},
            suggestion="尝试放慢语速，逐音节清晰发音：/ˈmaɪ.kroʊˌsɜːr.vɪ.sɪz/",
            display_priority=1,
        ),
        TimelineEvent(
            interview_id=DEMO_SESSION_ID,
            turn_id="turn_004",
            event_type="grammar",
            severity="minor",
            title="轻微语法纠正",
            description="表述中有冗余修正 'I also designed... I have designed'，建议直接说 'I have also designed'",
            start_ms=35000, end_ms=38000,
            transcript_snippet="I also designed... I have designed indexing strategies for tenant-scoped queries.",
            evidence={"original": "I also designed... I have designed", "corrected": "I have also designed"},
            suggestion="自我修正是好的，但可在开口前稍作停顿整理思路，减少中途修正",
            display_priority=3,
        ),
        TimelineEvent(
            interview_id=DEMO_SESSION_ID,
            turn_id="turn_004",
            event_type="filler_word",
            severity="low",
            title="语气词过多",
            description="此轮出现 2 次 'um' 和 1 次 'uh'，影响流利度评分",
            start_ms=34000, end_ms=42000,
            transcript_snippet="We implemented a dead letter queue... um... we used circuit breakers... uh... 99.9% uptime",
            evidence={"fillerWords": ["um", "um", "uh"], "count": 3},
            suggestion="在思考时可用短暂停顿替代语气词，或使用 'let me think' 等过渡语",
            display_priority=2,
        ),
        TimelineEvent(
            interview_id=DEMO_SESSION_ID,
            turn_id="turn_008",
            event_type="highlight",
            severity="low",
            title="亮点：系统设计思路清晰",
            description="对实时通知系统的设计回答逻辑清晰，涵盖 WebSocket、Kafka、离线消息存储三个层面",
            start_ms=82000, end_ms=98000,
            transcript_snippet="I would use WebSocket connections with a pub-sub model... For offline users, we store notifications in a database...",
            evidence={"dimensions": ["logic", "technical", "communication"]},
            suggestion="继续保持这种结构化表达方式",
            display_priority=5,
        ),
        TimelineEvent(
            interview_id=DEMO_SESSION_ID,
            turn_id="turn_010",
            event_type="highlight",
            severity="low",
            title="亮点：技术权衡意识强",
            description="清晰阐述了 CAP 理论在实际工程中的应用，展示了成熟的工程思维",
            start_ms=106000, end_ms=122000,
            transcript_snippet="We chose eventual consistency with idempotency keys to ensure no double-charging...",
            evidence={"dimensions": ["logic", "technical", "confidence"]},
            suggestion="可以补充提及这个决策的业务影响指标",
            display_priority=4,
        ),
    ]
    for event in timeline_events:
        session.add(event)

    # 3) 创建 Report 记录
    report = Report(
        interview_id=DEMO_SESSION_ID,
        scene_score=78,
        score_name="Offer Score",
        dimension_scores={
            "english": 80,
            "logic": 75,
            "confidence": 70,
            "star": 72,
            "technical": 82,
            "communication": 78,
        },
        report_json={
            "finalRecommendation": "候选人后端技术基础扎实，系统设计能力突出。表达清晰有条理，但存在少量语气词（um/uh）和语法修正。建议在正式面试前练习减少语气词使用，放慢语速以确保关键词发音准确。总体评分 78/100，具备进入下一轮面试的能力。",
            "highlights": [
                "实时通知系统架构设计回答完整，涵盖 WebSocket、Kafka、离线消息存储三个维度",
                "CAP 理论实际应用理解深刻，能清晰阐述 consistency vs availability 的工程权衡",
                "分布式系统经验丰富，有千万级日处理量的实际项目经历",
            ],
            "improvements": [
                "减少语气词使用：本次对话出现 2 次 'um' 和 1 次 'uh'，建议用短暂停顿替代",
                "关键词发音：'microservices'、'circuit'、'cascade' 等专业词汇发音需加强",
                "减少中途语法修正：turn_006 中出现一次自我打断修正，建议先构思再开口",
            ],
            "dimensionEvidence": {
                "english": {"score": 80, "evidence": "词汇丰富，专业术语使用恰当，偶有语法小失误但不影响理解"},
                "logic": {"score": 75, "evidence": "系统设计回答逻辑清晰，但部分回答结构可更 STAR 化"},
                "confidence": {"score": 70, "evidence": "有自我修正和语气词使用，影响表达流畅度和信心感"},
                "star": {"score": 72, "evidence": "项目经验描述有 STAR 框架意识，但 Situation 和 Result 部分可以更具体"},
                "technical": {"score": 82, "evidence": "分布式系统、数据库设计、消息队列等核心技术领域知识扎实"},
                "communication": {"score": 78, "evidence": "表达自然流畅，能清晰解释复杂技术概念"},
            },
            "generatedBy": "seed",
        },
    )
    session.add(report)
    await session.commit()
    print(f"[OfferGPT] Demo session seeded: {DEMO_SESSION_ID}")
