"""Application configuration – env vars > root .env.local > backend .env > defaults."""

from pathlib import Path
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


def _env_files():
    """返回环境变量文件列表，后者优先覆盖前者。"""
    files = []
    backend_env = Path(__file__).resolve().parent / ".env"
    if backend_env.exists():
        files.append(str(backend_env))
    root_local = ROOT_DIR / ".env.local"
    if root_local.exists():
        files.append(str(root_local))
    return files if files else None


def _normalize_llm_model(name: str) -> str:
    """将环境变量中的模型名规范为 DeepSeek API 接受的格式。"""
    key = (name or "").strip().lower().replace("_", "-")
    aliases = {
        "deepseekv4pro": "deepseek-v4-pro",
        "deepseek-v4-pro": "deepseek-v4-pro",
        "deepseek-v4-flash": "deepseek-v4-flash",
    }
    return aliases.get(key, name)


class Settings(BaseSettings):
    """OfferGPT backend settings."""

    model_config = SettingsConfigDict(
        env_file=_env_files(), env_file_encoding="utf-8", extra="ignore"
    )

    # ---- App ----
    app_env: str = "development"
    log_level: str = "INFO"
    demo_mode_enabled: bool = True

    # ---- Server ----
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    ws_base_url: str = "ws://localhost:8000"
    cors_allow_origins: str = "http://localhost:3000"
    session_token_secret: str = "dev-secret-change-me"
    session_ttl_seconds: int = 7200

    # ---- DB ----
    database_url: str = "sqlite+aiosqlite:///./offergpt.db"

    # ---- Redis ----
    redis_url: str = "redis://localhost:6379/1"

    # ---- Scene ----
    default_scene: str = "interview"
    enable_restaurant_scene: bool = False
    enable_meeting_scene: bool = False
    realtime_light_correction_enabled: bool = True

    # ---- LLM ----
    llm_provider: str = "deepseek"
    llm_api_base_url: str = "https://api.deepseek.com/anthropic"
    llm_model: str = "deepseek-v4-flash"
    llm_report_model: str = "deepseek-v4-pro"
    llm_analysis_model: str = "deepseek-v4-pro"
    llm_api_key: str = ""
    deepseek_api_key: str = ""

    @field_validator("llm_model", "llm_report_model", "llm_analysis_model", mode="before")
    @classmethod
    def normalize_llm_model_fields(cls, value: str) -> str:
        return _normalize_llm_model(value)

    # ---- ASR/TTS ----
    asr_provider: str = "whisper"
    asr_api_base_url: str = ""
    asr_model: str = "tiny"
    vad_silence_ms: int = 500
    vad_speech_start_frames: int = 5
    inactivity_prompt_sec: int = 90
    inactivity_close_after_prompt_sec: int = 30
    openai_api_key: str = ""
    tts_provider: str = "edgeTts"
    tts_voice: str = "en-US-JennyNeural"
    enable_mock_asr: bool = False
    enable_mock_tts: bool = False
    # 默认关闭服务端 Edge TTS，由前端浏览器 speechSynthesis 朗读（更低延迟）
    enable_server_tts: bool = False

    # ---- 发音/语法分析 ----
    pronunciation_low_confidence_threshold: float = 0.6
    pause_silence_ms: int = 300
    grammar_llm_timeout_sec: float = 5.0

    # ---- Derived (keep old attribute names for compat) ----
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def env(self) -> str:
        return self.app_env

    @property
    def host(self) -> str:
        return self.backend_host

    @property
    def port(self) -> int:
        return self.backend_port

    @property
    def cors_origins(self) -> str:
        return self.cors_allow_origins

    @property
    def is_development(self) -> bool:
        return self.app_env in ("development", "demo")


settings = Settings()
