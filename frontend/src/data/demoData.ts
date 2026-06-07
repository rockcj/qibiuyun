/**
 * Demo 静态兜底数据 — 当后端 /api/demo 和 localStorage 缓存均不可用时使用。
 * 数据与 backend/database.py 中的 _seed_demo_session 保持一致。
 */

import type {
  SessionAnalysisResponse,
  SessionReportResponse,
  SessionEventsResponse,
} from "@/types/api";

export const DEMO_SESSION_ID = "de000001-0000-0000-0000-000000000001";

export const FALLBACK_DEMO_ANALYSIS: SessionAnalysisResponse = {
  sessionId: DEMO_SESSION_ID,
  pronunciation: [
    {
      turnId: "turn_002",
      wordsPerMinute: 135,
      pauseCount: 2,
      lowConfidenceWords: ["microservices"],
      durationSeconds: 13,
      wordCount: 29,
      overallConfidence: 0.85,
    },
    {
      turnId: "turn_004",
      wordsPerMinute: 120,
      pauseCount: 4,
      lowConfidenceWords: ["circuit", "cascade"],
      durationSeconds: 17,
      wordCount: 34,
      overallConfidence: 0.72,
    },
    {
      turnId: "turn_006",
      wordsPerMinute: 110,
      pauseCount: 3,
      lowConfidenceWords: ["tenant-scoped"],
      durationSeconds: 15,
      wordCount: 27,
      overallConfidence: 0.78,
    },
    {
      turnId: "turn_008",
      wordsPerMinute: 140,
      pauseCount: 1,
      lowConfidenceWords: [],
      durationSeconds: 16,
      wordCount: 37,
      overallConfidence: 0.90,
    },
    {
      turnId: "turn_010",
      wordsPerMinute: 130,
      pauseCount: 2,
      lowConfidenceWords: ["idempotency"],
      durationSeconds: 16,
      wordCount: 35,
      overallConfidence: 0.82,
    },
  ],
  corrections: [
    {
      turnId: "turn_004",
      original: "we um used circuit breakers",
      corrected: "we used circuit breakers",
      severity: "minor",
      transcript: "we um used circuit breakers",
    },
    {
      turnId: "turn_006",
      original: "I also designed... I have designed",
      corrected: "I have also designed",
      severity: "minor",
      transcript: "I also designed",
    },
  ],
  fillerCounts: { um: 2, uh: 1 },
  transcriptTurns: [
    {
      turnId: "turn_001",
      role: "assistant",
      text: "Hello! Welcome to the interview for the Backend Engineer position. Could you start by telling me about your experience with distributed systems?",
      startMs: 0,
      endMs: 8000,
    },
    {
      turnId: "turn_002",
      role: "user",
      text: "Sure! I have about five years of experience building microservices using Go and Python. At my last company, I designed a message queue system that handled over 10 million events per day.",
      startMs: 9000,
      endMs: 22000,
    },
    {
      turnId: "turn_003",
      role: "assistant",
      text: "That's impressive! How did you handle failure scenarios in that message queue system?",
      startMs: 23000,
      endMs: 30000,
    },
    {
      turnId: "turn_004",
      role: "user",
      text: "We implemented a dead letter queue for messages that failed after three retries. Also, we used... um... we used circuit breakers to prevent cascade failures. The system had... uh... 99.9% uptime over two years.",
      startMs: 31000,
      endMs: 48000,
    },
    {
      turnId: "turn_005",
      role: "assistant",
      text: "Great answer! Let me ask about your experience with database design. How would you model a multi-tenant SaaS application's data layer?",
      startMs: 49000,
      endMs: 56000,
    },
    {
      turnId: "turn_006",
      role: "user",
      text: "I would use a shared database with tenant ID column for isolation. Each table has a tenant_id foreign key. For high-security tenants, we can use separate schemas. I also designed... I have designed indexing strategies for tenant-scoped queries.",
      startMs: 57000,
      endMs: 72000,
    },
    {
      turnId: "turn_007",
      role: "assistant",
      text: "Excellent! Now let's discuss system design. How would you design a real-time notification system that can scale to millions of users?",
      startMs: 73000,
      endMs: 81000,
    },
    {
      turnId: "turn_008",
      role: "user",
      text: "I would use WebSocket connections with a pub-sub model. The notification service publishes events to Kafka, and each user's connection subscribes to their own topic. For offline users, we store notifications in a database and sync when they come back online.",
      startMs: 82000,
      endMs: 98000,
    },
    {
      turnId: "turn_009",
      role: "assistant",
      text: "That's a well-thought-out design. One final question: can you describe a time when you had to make a difficult technical trade-off?",
      startMs: 99000,
      endMs: 105000,
    },
    {
      turnId: "turn_010",
      role: "user",
      text: "Yes. We had to choose between consistency and availability for our payment system. We chose eventual consistency with idempotency keys to ensure no double-charging. This allowed us to keep the system available during peak traffic while maintaining data integrity.",
      startMs: 106000,
      endMs: 122000,
    },
  ],
};

export const FALLBACK_DEMO_REPORT: SessionReportResponse = {
  reportId: "rep_de000001-0000-0000-0000-000000000001",
  sessionId: DEMO_SESSION_ID,
  scene: "interview",
  scoreName: "Offer 评分",
  sceneScore: 78,
  dimensionScores: {
    english: 80,
    logic: 75,
    confidence: 70,
    star: 72,
    technical: 82,
    communication: 78,
  },
  finalRecommendation:
    "候选人后端技术基础扎实，系统设计能力突出。表达清晰有条理，但存在少量语气词（um/uh）和语法修正。建议在正式面试前练习减少语气词使用，放慢语速以确保关键词发音准确。总体评分 78/100，具备进入下一轮面试的能力。",
  highlights: [
    "实时通知系统架构设计回答完整，涵盖 WebSocket、Kafka、离线消息存储三个维度",
    "CAP 理论实际应用理解深刻，能清晰阐述 consistency vs availability 的工程权衡",
    "分布式系统经验丰富，有千万级日处理量的实际项目经历",
  ],
  improvements: [
    "减少语气词使用：本次对话出现 2 次 'um' 和 1 次 'uh'，建议用短暂停顿替代",
    "关键词发音：'microservices'、'circuit'、'cascade' 等专业词汇发音需加强",
    "减少中途语法修正：turn_006 中出现一次自我打断修正，建议先构思再开口",
  ],
  evidenceList: [
    { dimension: "english", score: 80, evidence: "词汇丰富，专业术语使用恰当，偶有语法小失误但不影响理解" },
    { dimension: "logic", score: 75, evidence: "系统设计回答逻辑清晰，但部分回答结构可更 STAR 化" },
    { dimension: "confidence", score: 70, evidence: "有自我修正和语气词使用，影响表达流畅度和信心感" },
    { dimension: "star", score: 72, evidence: "项目经验描述有 STAR 框架意识，但 Situation 和 Result 部分可以更具体" },
    { dimension: "technical", score: 82, evidence: "分布式系统、数据库设计、消息队列等核心技术领域知识扎实" },
    { dimension: "communication", score: 78, evidence: "表达自然流畅，能清晰解释复杂技术概念" },
  ],
  reportStatus: "ready",
};

export const FALLBACK_DEMO_EVENTS: SessionEventsResponse = {
  sessionId: DEMO_SESSION_ID,
  events: [
    {
      eventId: "evt_demo_001",
      turnId: "turn_002",
      eventType: "pronunciation",
      severity: "low",
      title: "发音纠正：microservices",
      description:
        "单词 'microservices' 发音置信度较低，建议拆分音节练习：mi-cro-ser-vi-ces",
      startMs: 12000,
      endMs: 14000,
      transcriptSnippet:
        "I have about five years of experience building microservices using Go and Python.",
      evidence: { confidence: 0.65, word: "microservices" },
      suggestion: "尝试放慢语速，逐音节清晰发音：/ˈmaɪ.kroʊˌsɜːr.vɪ.sɪz/",
      displayPriority: 1,
    },
    {
      eventId: "evt_demo_002",
      turnId: "turn_004",
      eventType: "grammar",
      severity: "medium",
      title: "轻微语法纠正",
      description:
        "表述中有冗余修正 'I also designed... I have designed'，建议直接说 'I have also designed'",
      startMs: 35000,
      endMs: 38000,
      transcriptSnippet:
        "I also designed... I have designed indexing strategies for tenant-scoped queries.",
      evidence: {
        original: "I also designed... I have designed",
        corrected: "I have also designed",
      },
      suggestion: "自我修正是好的，但可在开口前稍作停顿整理思路，减少中途修正",
      displayPriority: 3,
    },
    {
      eventId: "evt_demo_003",
      turnId: "turn_004",
      eventType: "filler_word",
      severity: "low",
      title: "语气词过多",
      description: "此轮出现 2 次 'um' 和 1 次 'uh'，影响流利度评分",
      startMs: 34000,
      endMs: 42000,
      transcriptSnippet:
        "We implemented a dead letter queue... um... we used circuit breakers... uh... 99.9% uptime",
      evidence: { fillerWords: ["um", "um", "uh"], count: 3 },
      suggestion: "在思考时可用短暂停顿替代语气词，或使用 'let me think' 等过渡语",
      displayPriority: 2,
    },
    {
      eventId: "evt_demo_004",
      turnId: "turn_008",
      eventType: "highlight",
      severity: "low",
      title: "亮点：系统设计思路清晰",
      description:
        "对实时通知系统的设计回答逻辑清晰，涵盖 WebSocket、Kafka、离线消息存储三个层面",
      startMs: 82000,
      endMs: 98000,
      transcriptSnippet:
        "I would use WebSocket connections with a pub-sub model... For offline users, we store notifications in a database...",
      evidence: { dimensions: ["logic", "technical", "communication"] },
      suggestion: "继续保持这种结构化表达方式",
      displayPriority: 5,
    },
    {
      eventId: "evt_demo_005",
      turnId: "turn_010",
      eventType: "highlight",
      severity: "low",
      title: "亮点：技术权衡意识强",
      description:
        "清晰阐述了 CAP 理论在实际工程中的应用，展示了成熟的工程思维",
      startMs: 106000,
      endMs: 122000,
      transcriptSnippet:
        "We chose eventual consistency with idempotency keys to ensure no double-charging...",
      evidence: { dimensions: ["logic", "technical", "confidence"] },
      suggestion: "可以补充提及这个决策的业务影响指标",
      displayPriority: 4,
    },
  ],
};
