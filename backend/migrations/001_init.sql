-- OfferGPT Database Migration v001
-- Target: PostgreSQL 15+
-- This migration creates the core tables for the multi-scene training platform.

BEGIN;

-- ============================================================================
-- users
-- ============================================================================
CREATE TABLE IF NOT EXISTS users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) NOT NULL UNIQUE,
    name        VARCHAR(100),
    avatar_url  TEXT,
    plan        VARCHAR(50)  NOT NULL DEFAULT 'free',
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- ============================================================================
-- resumes
-- ============================================================================
CREATE TABLE IF NOT EXISTS resumes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_url       TEXT,
    file_type      VARCHAR(20)  NOT NULL,
    raw_text       TEXT,
    parsed_profile JSONB        NOT NULL DEFAULT '{}',
    parse_status   VARCHAR(30)  NOT NULL DEFAULT 'pending',
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_resumes_user_id ON resumes(user_id, created_at DESC);

-- ============================================================================
-- jobs
-- ============================================================================
CREATE TABLE IF NOT EXISTS jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title            VARCHAR(200) NOT NULL,
    company          VARCHAR(200),
    jd_text          TEXT         NOT NULL,
    parsed_profile   JSONB        NOT NULL DEFAULT '{}',
    difficulty_level VARCHAR(30),
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_jobs_user_id ON jobs(user_id, created_at DESC);

-- ============================================================================
-- scene_presets
-- ============================================================================
CREATE TABLE IF NOT EXISTS scene_presets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID REFERENCES users(id) ON DELETE SET NULL,
    scene        VARCHAR(30)  NOT NULL,
    topic        VARCHAR(80),
    role_mode    VARCHAR(80),
    scene_config JSONB        NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_scene_presets_scene ON scene_presets(scene);

-- ============================================================================
-- interviews  (multi-scene training sessions)
-- ============================================================================
CREATE TABLE IF NOT EXISTS interviews (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id        UUID REFERENCES resumes(id) ON DELETE SET NULL,
    job_id           UUID REFERENCES jobs(id) ON DELETE SET NULL,
    scene            VARCHAR(30)  NOT NULL,
    topic            VARCHAR(80),
    role_mode        VARCHAR(80),
    persona_mode     VARCHAR(50),
    scene_config     JSONB,
    status           VARCHAR(30)  NOT NULL DEFAULT 'created',
    duration_seconds INTEGER,
    transcript       JSONB,
    audio_url        TEXT,
    metrics_json     JSONB,
    started_at       TIMESTAMPTZ,
    ended_at         TIMESTAMPTZ,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_interviews_user_id ON interviews(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_interviews_user_scene ON interviews(user_id, scene, created_at DESC);
CREATE INDEX IF NOT EXISTS ix_interviews_status ON interviews(status, created_at);

-- ============================================================================
-- timeline_events
-- ============================================================================
CREATE TABLE IF NOT EXISTS timeline_events (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id       UUID         NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    turn_id            VARCHAR(80),
    event_type         VARCHAR(50)  NOT NULL,
    severity           VARCHAR(20)  DEFAULT 'medium',
    title              VARCHAR(200) NOT NULL,
    description        TEXT,
    start_ms           INTEGER      NOT NULL DEFAULT 0,
    end_ms             INTEGER      NOT NULL DEFAULT 0,
    transcript_snippet TEXT,
    evidence           JSONB,
    suggestion         TEXT,
    display_priority   INTEGER      DEFAULT 0,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_timeline_events_interview_start
    ON timeline_events(interview_id, start_ms);
CREATE INDEX IF NOT EXISTS ix_timeline_events_interview_type
    ON timeline_events(interview_id, event_type);

-- ============================================================================
-- reports
-- ============================================================================
CREATE TABLE IF NOT EXISTS reports (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id      UUID         NOT NULL UNIQUE REFERENCES interviews(id) ON DELETE CASCADE,
    scene_score       INTEGER,
    score_name        VARCHAR(80)  NOT NULL,
    dimension_scores  JSONB        NOT NULL DEFAULT '{}',
    report_json       JSONB        NOT NULL DEFAULT '{}',
    growth_plan_json  JSONB,
    twin_profile_json JSONB,
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_reports_scene_score ON reports(scene_score);

-- ============================================================================
-- agent_logs
-- ============================================================================
CREATE TABLE IF NOT EXISTS agent_logs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id     UUID         NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    turn_id          VARCHAR(80),
    agent_name       VARCHAR(80)  NOT NULL,
    model_name       VARCHAR(80),
    input_summary    JSONB,
    output_json      JSONB,
    latency_ms       INTEGER,
    prompt_tokens    INTEGER,
    completion_tokens INTEGER,
    error_message    TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agent_logs_interview_created
    ON agent_logs(interview_id, created_at);
CREATE INDEX IF NOT EXISTS ix_agent_logs_agent_created
    ON agent_logs(agent_name, created_at);

COMMIT;
