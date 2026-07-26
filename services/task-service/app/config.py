from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://task_service:task_service@localhost:5434/task_db"

    jwt_issuer: str = "user-service"
    jwt_secret_key: str = "change-me-shared-jwt-secret"


settings = Settings()
