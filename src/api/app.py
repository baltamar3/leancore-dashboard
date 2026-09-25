"""API FastAPI: endpoint de métricas y tablero HTML."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError

from src.aggregation.metrics import MinuteMetrics, get_metrics
from src.api.dashboard_html import DASHBOARD_HTML
from src.api.dependencies import get_redis
from src.config.settings import Settings, get_settings
from src.consumer.redis_client import create_redis

settings: Settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Abre el cliente Redis compartido al arrancar y lo cierra al apagar."""
    app.state.redis = create_redis(settings)
    yield
    await app.state.redis.aclose()


app = FastAPI(title="Payment Metrics Dashboard", lifespan=lifespan)


@app.get("/metrics/payments")
async def payments_metrics(
    minutes: int = Query(
        default=settings.default_metrics_minutes, ge=1, le=settings.max_metrics_minutes
    ),
    redis: Redis = Depends(get_redis),
) -> dict:
    """Devuelve el conteo `processed`/`failed` de los últimos `minutes` minutos."""
    try:
        metrics: list[MinuteMetrics] = await get_metrics(redis, minutes=minutes)
    except RedisError as exc:
        raise HTTPException(status_code=503, detail="Metrics storage unavailable") from exc

    return {
        "minutes": minutes,
        "buckets": [
            {
                "minute": bucket.minute_start.isoformat(),
                "processed": bucket.processed,
                "failed": bucket.failed,
            }
            for bucket in metrics
        ],
    }


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Sirve el tablero HTML (selector de ventana + serie de tiempo/agregado)."""
    return DASHBOARD_HTML
