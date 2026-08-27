from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CloudDesk Support Agent"
    app_env: str = "development"

    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/"
        "clouddesk_support"
    )

    gemini_api_key: str | None = None

    gemini_model: str = "gemini-3.5-flash-lite"

    gemini_embedding_model: str = "gemini-embedding-2"

    embedding_dimensions: int = 768

    knowledge_similarity_threshold: float = 0.50

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()