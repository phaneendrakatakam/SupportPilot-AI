from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SupportPilot AI"
    app_env: str = "development"
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/clouddesk_support"
    )
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_embedding_model: str = "gemini-embedding-2"
    embedding_dimensions: int = 768
    knowledge_min_score: float = 0.55
    max_agent_steps: int = 5

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
