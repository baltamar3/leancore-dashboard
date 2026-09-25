from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    redis_url: str = "redis://localhost:6379/0"

    stream_name: str = "stream:payments"
    consumer_group: str = "cg:payments-dashboard"
    dlq_stream_name: str = "stream:payments:dlq"

    # ADR 005: allowed lateness (segundos) es la garantía de que un evento tardío
    # cae en su bucket-minuto correcto; separado del TTL de dedupe y de la
    # retención del bucket, que solo acotan memoria.
    allowed_lateness_seconds: int = 5 * 60
    dedupe_ttl_seconds: int = 15 * 60
    bucket_retention_seconds: int = 2 * 60 * 60

    consumer_block_ms: int = 5_000
    consumer_batch_size: int = 50
    pending_min_idle_ms: int = 30_000
    max_delivery_attempts: int = 5

    reconnect_backoff_initial_seconds: float = 0.5
    reconnect_backoff_max_seconds: float = 30.0

    default_metrics_minutes: int = 15
    max_metrics_minutes: int = 120


def get_settings() -> Settings:
    return Settings()
