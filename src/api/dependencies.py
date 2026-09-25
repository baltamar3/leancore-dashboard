"""FastAPI dependencies injectable into the endpoints."""

from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """Return the shared Redis client created in the app's `lifespan`."""
    return request.app.state.redis
