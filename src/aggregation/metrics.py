"""Lectura de métricas agregadas por minuto desde Redis para la API del tablero."""

from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis

from src.aggregation.buckets import bucket_key, minute_range


@dataclass(frozen=True)
class MinuteMetrics:
    """Conteo de `processed`/`failed` para un bucket-minuto dado."""

    minute_start: datetime
    processed: int
    failed: int


async def get_metrics(
    redis: Redis, minutes: int, now: datetime | None = None
) -> list[MinuteMetrics]:
    """Lee los últimos `minutes` buckets (rellenando con cero los vacíos)."""
    now = now or datetime.now(timezone.utc)
    buckets: list[datetime] = minute_range(now, minutes)

    async with redis.pipeline(transaction=False) as pipe:
        for minute_start in buckets:
            pipe.hgetall(bucket_key(minute_start))
        raw_results: list[dict[bytes, bytes]] = await pipe.execute()

    metrics: list[MinuteMetrics] = []
    for minute_start, raw in zip(buckets, raw_results, strict=True):
        processed: int = int(raw.get(b"processed", 0))
        failed: int = int(raw.get(b"failed", 0))
        metrics.append(MinuteMetrics(minute_start=minute_start, processed=processed, failed=failed))
    return metrics
