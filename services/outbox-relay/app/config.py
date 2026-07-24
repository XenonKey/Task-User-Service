from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://task_service:task_service@localhost:5434/task_db"
    kafka_bootstrap_servers: str = "redpanda:9092"
    kafka_topic: str = "task-events"
    outbox_poll_interval_seconds: float = 3.0
    outbox_batch_size: int = 100


settings = Settings()
