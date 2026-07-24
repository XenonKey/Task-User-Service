from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://task_service:task_service@localhost:5434/task_db"

    user_service_jwks_url: str = "http://user-service:8000/.well-known/jwks.json"
    jwt_issuer: str = "user-service"
    jwks_fetch_retries: int = 15
    jwks_fetch_retry_delay_seconds: float = 2.0


settings = Settings()
