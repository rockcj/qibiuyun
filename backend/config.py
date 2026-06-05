"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """OfferGPT backend settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./offergpt.db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False

    # LLM API Keys
    openai_api_key: str = ""
    deepseek_api_key: str = ""

    # ASR/TTS
    asr_provider: str = "whisper"
    tts_provider: str = "edge"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:3000"
    env: str = "development"
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in self.cors_origins.split(",")]


settings = Settings()
