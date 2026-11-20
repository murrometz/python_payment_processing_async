from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    rabbitmq_url: str
    api_key: str

    # Echo of SQLAlchemy SQL-queries (by default)
    db_echo: bool = False

    outbox_poll_interval: float
    outbox_max_attempts: int
    webhook_timeout: float
    outbox_batch_size: int


settings = Settings()
