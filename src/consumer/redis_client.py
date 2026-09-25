"""Factory for the async Redis client shared by the API and the consumer."""

from redis.asyncio import Redis

from src.config.settings import Settings


def create_redis(settings: Settings) -> Redis:
    """Create an async Redis client from `settings.redis_url`."""
    return Redis.from_url(settings.redis_url)
