"""Dependencias de FastAPI inyectables en los endpoints."""

from fastapi import Request
from redis.asyncio import Redis


def get_redis(request: Request) -> Redis:
    """Devuelve el cliente Redis compartido, creado en el `lifespan` de la app."""
    return request.app.state.redis
