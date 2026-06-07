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
        await _seed_restaurant_demo_session(session, demo_user.id)
        await _seed_meeting_demo_session(session, demo_user.id)


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


async def _seed_restaurant_demo_session(session, demo_user_id):
    """预置 demo_restaurant_001 餐厅点餐训练会话：transcript + 报告 + VAR 事件。"""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from models.base import Interview, TimelineEvent, Report
    import uuid as _uuid

    DEMO_RESTAURANT_ID = _uuid.UUID("de000002-0000-0000-0000-000000000002")

    existing = await session.execute(
        select(Interview).where(Interview.id == DEMO_RESTAURANT_ID)
    )
    if existing.scalar_one_or_none() is not None:
        print("[OfferGPT] Restaurant demo session already seeded, skipping")
        return

    interview = Interview(
        id=DEMO_RESTAURANT_ID,
        user_id=demo_user_id,
        scene="restaurant",
        topic="ordering",
        role_mode="friendlyWaiter",
        persona_mode="friendlyWaiter",
        scene_config={
            "scene": "restaurant",
            "topic": "ordering",
            "roleMode": "friendlyWaiter",
            "personaMode": "friendlyWaiter",
            "difficultyLevel": "middle",
            "durationMinutes": 12,
            "rubric": ["english", "politeness", "functionalPhrases", "taskCompletion", "pronunciationFluency"],
        },
        status="completed",
        duration_seconds=130,
        transcript={
            "turns": [
                {
                    "turnId": "turn_001", "role": "assistant",
                    "text": "Good evening! Welcome to The Garden Bistro. Here's your menu. Can I start you off with something to drink?",
                    "startMs": 0, "endMs": 6000,
                },
                {
                    "turnId": "turn_002", "role": "user",
                    "text": "Hi! Yes, I'd like a glass of sparkling water, please. And could you tell me about today's specials?",
                    "startMs": 7000, "endMs": 15000,
                },
                {
                    "turnId": "turn_003", "role": "assistant",
                    "text": "Of course! Today our chef is featuring a pan-seared salmon with lemon butter sauce, served with roasted asparagus. It's been very popular!",
                    "startMs": 16000, "endMs": 26000,
                },
                {
                    "turnId": "turn_004", "role": "user",
                    "text": "That sounds... um... delicious! I'll have the salmon. Could you ask the chef to make it well-done? And I'd like to substitute the asparagus with... uh... a side salad if possible.",
                    "startMs": 27000, "endMs": 42000,
                },
                {
                    "turnId": "turn_005", "role": "assistant",
                    "text": "Absolutely! Well-done salmon with a side salad — no problem at all. Would you like to add a starter? Our tomato basil soup is excellent today.",
                    "startMs": 43000, "endMs": 52000,
                },
                {
                    "turnId": "turn_006", "role": "user",
                    "text": "Yes, I'll take the tomato soup to start. And for dessert, do you have anything without gluten? I have a mild allergy.",
                    "startMs": 53000, "endMs": 65000,
                },
                {
                    "turnId": "turn_007", "role": "assistant",
                    "text": "Thank you for letting me know. Our flourless chocolate cake is completely gluten-free and very popular. I'll make a note for the kitchen about your allergy.",
                    "startMs": 66000, "endMs": 76000,
                },
                {
                    "turnId": "turn_008", "role": "user",
                    "text": "Perfect! I'll have the flourless chocolate cake then. Also, can I have the bill split? My friend and I are paying separately.",
                    "startMs": 77000, "endMs": 88000,
                },
                {
                    "turnId": "turn_009", "role": "assistant",
                    "text": "Of course, I'll split the bill for you. Let me confirm your order: tomato basil soup, well-done salmon with side salad, sparkling water, and flourless chocolate cake. Is that correct?",
                    "startMs": 89000, "endMs": 100000,
                },
                {
                    "turnId": "turn_010", "role": "user",
                    "text": "Yes, that's perfect. Thank you so much for being so helpful!",
                    "startMs": 101000, "endMs": 108000,
                },
            ],
        },
        metrics_json={
            "corrections": [
                {"turnId": "turn_004", "original": "That sounds... um... delicious", "corrected": "That sounds delicious", "severity": "minor", "transcript": "That sounds... um... delicious"},
                {"turnId": "turn_004", "original": "substitute the asparagus with... uh... a side salad", "corrected": "substitute the asparagus with a side salad", "severity": "minor", "transcript": "substitute the asparagus with... uh... a side salad"},
            ],
            "fillerCounts": {"um": 1, "uh": 1},
            "pronunciation": [
                {"turnId": "turn_002", "wordsPerMinute": 130, "pauseCount": 2, "lowConfidenceWords": ["sparkling"], "durationSeconds": 8, "wordCount": 17, "overallConfidence": 0.88},
                {"turnId": "turn_004", "wordsPerMinute": 115, "pauseCount": 5, "lowConfidenceWords": ["asparagus", "substitute"], "durationSeconds": 15, "wordCount": 29, "overallConfidence": 0.72},
                {"turnId": "turn_006", "wordsPerMinute": 125, "pauseCount": 3, "lowConfidenceWords": ["gluten"], "durationSeconds": 12, "wordCount": 25, "overallConfidence": 0.80},
                {"turnId": "turn_008", "wordsPerMinute": 140, "pauseCount": 1, "lowConfidenceWords": ["separately"], "durationSeconds": 11, "wordCount": 25, "overallConfidence": 0.85},
                {"turnId": "turn_010", "wordsPerMinute": 150, "pauseCount": 0, "lowConfidenceWords": [], "durationSeconds": 7, "wordCount": 18, "overallConfidence": 0.92},
            ],
        },
        started_at=datetime(2026, 6, 5, 14, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 6, 5, 14, 2, 10, tzinfo=timezone.utc),
    )
    session.add(interview)
    await session.flush()

    timeline_events = [
        TimelineEvent(
            interview_id=DEMO_RESTAURANT_ID,
            turn_id="turn_004",
            event_type="filler_word",
            severity="low",
            title="语气词：点餐时犹豫",
            description="点餐时出现 1 次 'um' 和 1 次 'uh'，影响表达流畅度",
            start_ms=27000, end_ms=42000,
            transcript_snippet="That sounds... um... delicious! I'll have the salmon... uh... a side salad if possible.",
            evidence={"fillerWords": ["um", "uh"], "count": 2},
            suggestion="点餐时可先看菜单整理思路，使用 'I'd like...' 直接开口，减少犹豫语气词",
            display_priority=2,
        ),
        TimelineEvent(
            interview_id=DEMO_RESTAURANT_ID,
            turn_id="turn_006",
            event_type="highlight",
            severity="low",
            title="亮点：主动提及过敏需求",
            description="自然地告知服务员麸质过敏，使用了得体的 'I have a mild allergy' 表达",
            start_ms=60000, end_ms=65000,
            transcript_snippet="And for dessert, do you have anything without gluten? I have a mild allergy.",
            evidence={"dimensions": ["politeness", "functionalPhrases", "taskCompletion"]},
            suggestion="主动告知过敏是餐厅场景中非常实用的技能，继续保持",
            display_priority=5,
        ),
        TimelineEvent(
            interview_id=DEMO_RESTAURANT_ID,
            turn_id="turn_008",
            event_type="highlight",
            severity="low",
            title="亮点：自然提出分账请求",
            description="使用 'Can I have the bill split?' 自然表达 AA 制需求，功能句型运用恰当",
            start_ms=82000, end_ms=88000,
            transcript_snippet="Also, can I have the bill split? My friend and I are paying separately.",
            evidence={"dimensions": ["functionalPhrases", "taskCompletion"]},
            suggestion="分账表达非常地道，'paying separately' 很好地解释了原因",
            display_priority=4,
        ),
        TimelineEvent(
            interview_id=DEMO_RESTAURANT_ID,
            turn_id="turn_002",
            event_type="highlight",
            severity="low",
            title="亮点：开场礼貌且主动",
            description="使用 'I'd like' 和 'Could you tell me' 等礼貌句型，符合餐厅场景交际礼仪",
            start_ms=7000, end_ms=15000,
            transcript_snippet="Hi! Yes, I'd like a glass of sparkling water, please. And could you tell me about today's specials?",
            evidence={"dimensions": ["english", "politeness"]},
            suggestion="开场表达礼貌得体，句式丰富，是很好的餐厅英语范本",
            display_priority=3,
        ),
        TimelineEvent(
            interview_id=DEMO_RESTAURANT_ID,
            turn_id="turn_004",
            event_type="pronunciation",
            severity="low",
            title="发音提示：asparagus",
            description="单词 'asparagus' 发音置信度较低，建议拆分音节练习",
            start_ms=38000, end_ms=40000,
            transcript_snippet="I'd like to substitute the asparagus with a side salad if possible.",
            evidence={"confidence": 0.62, "word": "asparagus"},
            suggestion="'asparagus' 发音：/əˈspær.ə.ɡəs/，重音在第二个音节",
            display_priority=1,
        ),
    ]
    for event in timeline_events:
        session.add(event)

    report = Report(
        interview_id=DEMO_RESTAURANT_ID,
        scene_score=82,
        score_name="点餐评分",
        dimension_scores={
            "english": 83,
            "politeness": 88,
            "functionalPhrases": 85,
            "taskCompletion": 80,
            "pronunciationFluency": 74,
        },
        report_json={
            "finalRecommendation": "餐厅点餐英语整体表现优秀。礼貌用语使用得体，功能句型（点餐、分账、过敏说明）覆盖全面。存在少量语气词和个别单词发音不准，但不影响沟通。建议继续练习不同服务员角色（如忙碌/不耐烦），提升应对压力场景的能力。总体评分 82/100。",
            "highlights": [
                "过敏需求表达自然：主动告知麸质过敏，使用 'I have a mild allergy' 安全警示句型",
                "分账请求地道：'split the bill' + 'paying separately' 完整表达 AA 制需求",
                "开场礼貌得体：使用 'I'd like'、'Could you tell me' 等多样句式",
            ],
            "improvements": [
                "减少语气词：点餐时出现 'um' 和 'uh'，建议用短暂停顿替代犹豫填充词",
                "发音练习：'asparagus' /əˈspær.ə.ɡəs/ 和 'sparkling' 需要重点练习",
                "可尝试更复杂的场景：如投诉处理、特殊要求（靠窗座位/包间）",
            ],
            "dimensionEvidence": {
                "english": {"score": 83, "evidence": "词汇使用准确，句式多样，能清晰表达点餐需求"},
                "politeness": {"score": 88, "evidence": "'please'、'thank you'、'could you' 等礼貌用语使用频繁且自然"},
                "functionalPhrases": {"score": 85, "evidence": "点餐、替换配菜、过敏说明、分账请求等功能句型覆盖全面"},
                "taskCompletion": {"score": 80, "evidence": "成功完成完整点餐流程，包括饮料、主菜、甜点、分账"},
                "pronunciationFluency": {"score": 74, "evidence": "整体流利但存在 2 次犹豫停顿和个别词汇发音欠佳"},
            },
            "generatedBy": "seed",
        },
    )
    session.add(report)
    await session.commit()
    print(f"[OfferGPT] Restaurant demo session seeded: {DEMO_RESTAURANT_ID}")


async def _seed_meeting_demo_session(session, demo_user_id):
    """预置 demo_meeting_001 商务会议训练会话：transcript + 报告 + VAR 事件。"""
    from datetime import datetime, timezone
    from sqlalchemy import select
    from models.base import Interview, TimelineEvent, Report
    import uuid as _uuid

    DEMO_MEETING_ID = _uuid.UUID("de000003-0000-0000-0000-000000000003")

    existing = await session.execute(
        select(Interview).where(Interview.id == DEMO_MEETING_ID)
    )
    if existing.scalar_one_or_none() is not None:
        print("[OfferGPT] Meeting demo session already seeded, skipping")
        return

    interview = Interview(
        id=DEMO_MEETING_ID,
        user_id=demo_user_id,
        scene="meeting",
        topic="projectUpdate",
        role_mode="meetingHost",
        persona_mode="meetingHost",
        scene_config={
            "scene": "meeting",
            "topic": "projectUpdate",
            "roleMode": "meetingHost",
            "personaMode": "meetingHost",
            "difficultyLevel": "middle",
            "durationMinutes": 15,
            "rubric": ["english", "logic", "communication", "functionalPhrases", "meetingControl"],
        },
        status="completed",
        duration_seconds=160,
        transcript={
            "turns": [
                {
                    "turnId": "turn_001", "role": "assistant",
                    "text": "Alright, let's get started. First on the agenda — Sarah, can you give us a quick update on the mobile app redesign project? Where are we with the timeline?",
                    "startMs": 0, "endMs": 9000,
                },
                {
                    "turnId": "turn_002", "role": "user",
                    "text": "Thanks, Mike. The mobile app redesign is... um... progressing well. We completed the UI components library last week, but we're about three days behind on the onboarding flow because of some unexpected API changes from the backend team.",
                    "startMs": 10000, "endMs": 26000,
                },
                {
                    "turnId": "turn_003", "role": "assistant",
                    "text": "Three days behind — that's concerning. What's the main blocker, and do you need any additional resources to get back on track?",
                    "startMs": 27000, "endMs": 36000,
                },
                {
                    "turnId": "turn_004", "role": "user",
                    "text": "The main blocker is the authentication API. The backend team changed the endpoint signatures without updating the documentation first. I've already scheduled a sync meeting with them for tomorrow morning. I think we can catch up by next week if we prioritize the remaining sprints.",
                    "startMs": 37000, "endMs": 54000,
                },
                {
                    "turnId": "turn_005", "role": "assistant",
                    "text": "Good, proactive move on the sync meeting. Can you quantify the impact — will this delay affect the Q3 launch date? And what's your mitigation plan if the API issues aren't resolved by end of week?",
                    "startMs": 55000, "endMs": 67000,
                },
                {
                    "turnId": "turn_006", "role": "user",
                    "text": "If we resolve the API issues this week, Q3 launch is still achievable. However... uh... if it drags into next week, we might need to descope the social sharing feature and push it to Q4. I've prepared a risk assessment document with three scenarios that I can share after this meeting.",
                    "startMs": 68000, "endMs": 86000,
                },
                {
                    "turnId": "turn_007", "role": "assistant",
                    "text": "A risk assessment with three scenarios — that's exactly what we need. Please share that with the full team by end of day. Now, any dependencies or support you need from other teams?",
                    "startMs": 87000, "endMs": 97000,
                },
                {
                    "turnId": "turn_008", "role": "user",
                    "text": "Yes, I need the QA team to allocate two more engineers for integration testing starting next Monday. Also, I'd like to request that the backend team appoint a dedicated API liaison for the remainder of this project to prevent similar issues.",
                    "startMs": 98000, "endMs": 113000,
                },
                {
                    "turnId": "turn_009", "role": "assistant",
                    "text": "Reasonable requests. I'll follow up with the QA lead and backend manager today. To summarize the action items: Sarah will lead the backend sync tomorrow, share the risk assessment by EOD, and we'll revisit the Q3 timeline on Friday. Does that cover everything?",
                    "startMs": 114000, "endMs": 126000,
                },
                {
                    "turnId": "turn_010", "role": "user",
                    "text": "Yes, that covers all the key points. Thank you for the support, Mike. I'll send out the meeting notes with the action items within the hour.",
                    "startMs": 127000, "endMs": 136000,
                },
            ],
        },
        metrics_json={
            "corrections": [
                {"turnId": "turn_002", "original": "The mobile app redesign is... um... progressing well", "corrected": "The mobile app redesign is progressing well", "severity": "minor", "transcript": "The mobile app redesign is... um... progressing well"},
                {"turnId": "turn_006", "original": "if it drags into next week... uh... we might", "corrected": "if it drags into next week, we might", "severity": "minor", "transcript": "if it drags into next week... uh... we might"},
            ],
            "fillerCounts": {"um": 1, "uh": 1},
            "pronunciation": [
                {"turnId": "turn_002", "wordsPerMinute": 130, "pauseCount": 3, "lowConfidenceWords": ["onboarding"], "durationSeconds": 16, "wordCount": 35, "overallConfidence": 0.80},
                {"turnId": "turn_004", "wordsPerMinute": 140, "pauseCount": 2, "lowConfidenceWords": ["authentication", "endpoint"], "durationSeconds": 17, "wordCount": 40, "overallConfidence": 0.76},
                {"turnId": "turn_006", "wordsPerMinute": 125, "pauseCount": 4, "lowConfidenceWords": ["descope", "mitigation"], "durationSeconds": 18, "wordCount": 38, "overallConfidence": 0.73},
                {"turnId": "turn_008", "wordsPerMinute": 145, "pauseCount": 1, "lowConfidenceWords": ["liaison"], "durationSeconds": 15, "wordCount": 36, "overallConfidence": 0.84},
                {"turnId": "turn_010", "wordsPerMinute": 155, "pauseCount": 1, "lowConfidenceWords": [], "durationSeconds": 9, "wordCount": 23, "overallConfidence": 0.90},
            ],
        },
        started_at=datetime(2026, 6, 6, 9, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 6, 6, 9, 2, 40, tzinfo=timezone.utc),
    )
    session.add(interview)
    await session.flush()

    timeline_events = [
        TimelineEvent(
            interview_id=DEMO_MEETING_ID,
            turn_id="turn_004",
            event_type="highlight",
            severity="low",
            title="亮点：主动推动问题解决",
            description="发现阻塞后主动安排同步会议，展现了良好的项目管理和主动性",
            start_ms=42000, end_ms=48000,
            transcript_snippet="I've already scheduled a sync meeting with them for tomorrow morning. I think we can catch up by next week.",
            evidence={"dimensions": ["communication", "meetingControl"]},
            suggestion="主动安排解决会议是优秀的会议沟通表现，继续保持这种推动力",
            display_priority=5,
        ),
        TimelineEvent(
            interview_id=DEMO_MEETING_ID,
            turn_id="turn_006",
            event_type="highlight",
            severity="low",
            title="亮点：风险评估意识强",
            description="准备了三种场景的风险评估文档，展示了对项目管理的专业素养",
            start_ms=78000, end_ms=86000,
            transcript_snippet="I've prepared a risk assessment document with three scenarios that I can share after this meeting.",
            evidence={"dimensions": ["logic", "communication"]},
            suggestion="提前准备风险文档是非常专业的做法，给团队提供了决策依据",
            display_priority=4,
        ),
        TimelineEvent(
            interview_id=DEMO_MEETING_ID,
            turn_id="turn_008",
            event_type="highlight",
            severity="low",
            title="亮点：清晰的资源请求",
            description="明确提出 QA 资源和 API 联络人的具体需求，资源请求表达清晰有力",
            start_ms=98000, end_ms=113000,
            transcript_snippet="I need the QA team to allocate two more engineers for integration testing...",
            evidence={"dimensions": ["functionalPhrases", "communication"]},
            suggestion="资源请求具体明确（两个工程师、指定联络人），是可执行的 Action Item",
            display_priority=3,
        ),
        TimelineEvent(
            interview_id=DEMO_MEETING_ID,
            turn_id="turn_002",
            event_type="filler_word",
            severity="low",
            title="语气词：开场汇报时犹豫",
            description="开场汇报时出现 'um' 犹豫填充词，影响专业形象",
            start_ms=12000, end_ms=14000,
            transcript_snippet="The mobile app redesign is... um... progressing well.",
            evidence={"fillerWords": ["um"], "count": 1},
            suggestion="开场汇报可提前准备提纲，用 'Here's where we stand:' 替代犹豫开头",
            display_priority=2,
        ),
        TimelineEvent(
            interview_id=DEMO_MEETING_ID,
            turn_id="turn_004",
            event_type="pronunciation",
            severity="low",
            title="发音提示：authentication",
            description="单词 'authentication' 发音置信度较低，是会议场景常见关键术语",
            start_ms=39000, end_ms=41000,
            transcript_snippet="The main blocker is the authentication API.",
            evidence={"confidence": 0.64, "word": "authentication"},
            suggestion="'authentication' 发音：/ɔːˌθen.tɪˈkeɪ.ʃən/，重音在第五音节 'ca'",
            display_priority=1,
        ),
    ]
    for event in timeline_events:
        session.add(event)

    report = Report(
        interview_id=DEMO_MEETING_ID,
        scene_score=79,
        score_name="会议评分",
        dimension_scores={
            "english": 81,
            "logic": 82,
            "communication": 83,
            "functionalPhrases": 78,
            "meetingControl": 74,
        },
        report_json={
            "finalRecommendation": "商务会议英语整体表现良好。项目汇报逻辑清晰，能主动推动问题解决并准备风险评估文档，展现了优秀的项目管理沟通能力。存在少量语气词和个别术语发音问题。建议继续练习不同会议角色（如向上级汇报、向同事质疑），提升会议掌控力。总体评分 79/100。",
            "highlights": [
                "主动推动解决：发现阻塞后立即安排同步会议，展现 owner 意识",
                "风险评估专业：提前准备三场景分析文档，为团队提供决策依据",
                "资源请求清晰：明确提出 QA 工程师数量和 API 联络人需求",
            ],
            "improvements": [
                "减少开场语气词：用准备充分的提纲开场，替代 'um' 等犹豫填充词",
                "术语发音练习：'authentication'、'onboarding'、'liaison' 等会议高频词汇需加强",
                "可尝试在会议中使用更多 'agree/disagree politely' 和 'interrupt politely' 的表达",
            ],
            "dimensionEvidence": {
                "english": {"score": 81, "evidence": "专业术语使用恰当，句式丰富，能清晰表达项目状态和需求"},
                "logic": {"score": 82, "evidence": "问题→原因→解决→风险的逻辑链完整，三场景风险分析展现结构化思维"},
                "communication": {"score": 83, "evidence": "信息传递清晰，主动同步进展和风险，沟通风格专业得体"},
                "functionalPhrases": {"score": 78, "evidence": "'I need', 'I'd like to request', 'I think we can' 等功能句型使用得当"},
                "meetingControl": {"score": 74, "evidence": "能响应会议主持人的引导，但在主动推进议程方面还有提升空间"},
            },
            "generatedBy": "seed",
        },
    )
    session.add(report)
    await session.commit()
    print(f"[OfferGPT] Meeting demo session seeded: {DEMO_MEETING_ID}")
