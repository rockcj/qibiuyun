"""SQLAlchemy ORM models for OfferGPT."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, relationship


def utcnow():
    return datetime.now(timezone.utc)


def new_uuid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Use JSON (not JSONB) for SQLite compatibility; PostgreSQL JSONB preferred.
# In production with PostgreSQL, swap JSON → JSONB via Alembic migration.
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=new_uuid)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(100), nullable=True)
    avatar_url = Column(Text, nullable=True)
    plan = Column(String(50), default="free")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    resumes = relationship("Resume", back_populates="user")
    jobs = relationship("Job", back_populates="user")
    interviews = relationship("Interview", back_populates="user")
    scene_presets = relationship("ScenePreset", back_populates="user")


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    file_url = Column(Text, nullable=True)
    file_type = Column(String(20), nullable=False)
    raw_text = Column(Text, nullable=True)
    parsed_profile = Column(String(4096), nullable=False, default="{}")  # JSON string for SQLite compat
    parse_status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="resumes")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    title = Column(String(200), nullable=False)
    company = Column(String(200), nullable=True)
    jd_text = Column(Text, nullable=False)
    parsed_profile = Column(String(4096), nullable=False, default="{}")
    difficulty_level = Column(String(30), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="jobs")


class ScenePreset(Base):
    __tablename__ = "scene_presets"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    scene = Column(String(30), index=True, nullable=False)
    topic = Column(String(80), nullable=True)
    role_mode = Column(String(80), nullable=True)
    scene_config = Column(String(8192), nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="scene_presets")


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String(36), primary_key=True, default=new_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    resume_id = Column(String(36), ForeignKey("resumes.id"), nullable=True)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)
    scene = Column(String(30), index=True, nullable=False)
    topic = Column(String(80), nullable=True)
    role_mode = Column(String(80), nullable=True)
    persona_mode = Column(String(50), nullable=True)
    scene_config = Column(String(8192), nullable=True)
    status = Column(String(30), index=True, default="created")
    duration_seconds = Column(Integer, nullable=True)
    transcript = Column(String(16384), nullable=True)
    audio_url = Column(Text, nullable=True)
    metrics_json = Column(String(4096), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    user = relationship("User", back_populates="interviews")
    timeline_events = relationship("TimelineEvent", back_populates="interview")
    report = relationship("Report", back_populates="interview", uselist=False)
    agent_logs = relationship("AgentLog", back_populates="interview")

    __table_args__ = (
        Index("ix_interviews_user_scene", "user_id", "scene", "created_at"),
    )


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    interview_id = Column(
        String(36), ForeignKey("interviews.id"), index=True, nullable=False
    )
    turn_id = Column(String(80), index=True, nullable=True)
    event_type = Column(String(50), index=True, nullable=False)
    severity = Column(String(20), index=True, nullable=True, default="medium")
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    start_ms = Column(Integer, nullable=False, default=0)
    end_ms = Column(Integer, nullable=False, default=0)
    transcript_snippet = Column(Text, nullable=True)
    evidence = Column(String(4096), nullable=True)
    suggestion = Column(Text, nullable=True)
    display_priority = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    interview = relationship("Interview", back_populates="timeline_events")

    __table_args__ = (
        Index("ix_timeline_events_interview_start", "interview_id", "start_ms"),
        Index("ix_timeline_events_interview_type", "interview_id", "event_type"),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=new_uuid)
    interview_id = Column(
        String(36), ForeignKey("interviews.id"), unique=True, nullable=False
    )
    scene_score = Column(Integer, index=True, nullable=True, default=0)
    score_name = Column(String(80), nullable=False)
    dimension_scores = Column(String(4096), nullable=False, default="{}")
    report_json = Column(String(16384), nullable=False, default="{}")
    growth_plan_json = Column(String(8192), nullable=True)
    twin_profile_json = Column(String(8192), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    interview = relationship("Interview", back_populates="report")


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id = Column(String(36), primary_key=True, default=new_uuid)
    interview_id = Column(
        String(36), ForeignKey("interviews.id"), index=True, nullable=False
    )
    turn_id = Column(String(80), nullable=True)
    agent_name = Column(String(80), index=True, nullable=False)
    model_name = Column(String(80), nullable=True)
    input_summary = Column(String(4096), nullable=True)
    output_json = Column(String(8192), nullable=True)
    latency_ms = Column(Integer, nullable=True)
    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    interview = relationship("Interview", back_populates="agent_logs")

    __table_args__ = (
        Index("ix_agent_logs_interview_created", "interview_id", "created_at"),
    )
