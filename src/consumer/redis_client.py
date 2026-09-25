"""Factory del cliente Redis asíncrono compartido por API y consumidor."""

from redis.asyncio import Redis

from src.config.settings import Settings


def create_redis(settings: Settings) -> Redis:
    """Crea un cliente Redis asíncrono a partir de `settings.redis_url`."""
    return Redis.from_url(settings.redis_url)
