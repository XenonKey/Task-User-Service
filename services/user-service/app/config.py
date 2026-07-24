from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://user_service:user_service@localhost:5433/user_db"
    admin_bootstrap_secret: str = "change-me"

    access_token_expire_minutes: int = 15
    refresh_token_expire_minutes: int = 10080
    jwt_issuer: str = "user-service"
    jwt_key_id: str = "user-service-key-1"

    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_topic: str = "task-events"
    kafka_consumer_group: str = "user-service-balance"


settings = Settings()
