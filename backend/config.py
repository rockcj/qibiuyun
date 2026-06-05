"""Application configuration – env vars > root .env.local > backend .env > defaults."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent


def _env_files():
    files = []
    root_local = ROOT_DIR / ".env.local"
    if root_local.exists():
        files.append(str(root_local))
    backend_env = Path(__file__).resolve().parent / ".env"
    if backend_env.exists():
        files.append(str(backend_env))
    return files if files else None


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
    llm_model: str = "deepseekV4pro"
    llm_report_model: str = "deepseekV4pro"
    llm_api_key: str = ""
    deepseek_api_key: str = ""

    # ---- ASR/TTS ----
    asr_provider: str = "whisper"
    asr_model: str = "whisper-1"
    tts_provider: str = "edgeTts"
    tts_voice: str = "en-US-JennyNeural"
    enable_mock_asr: bool = True
    enable_mock_tts: bool = True

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
