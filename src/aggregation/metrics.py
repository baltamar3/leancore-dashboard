from dataclasses import dataclass
from datetime import datetime, timezone

from redis.asyncio import Redis

from src.aggregation.buckets import bucket_key, minute_range


@dataclass(frozen=True)
class MinuteMetrics:
    minute_start: datetime
    processed: int
    failed: int


async def get_metrics(
    redis: Redis, minutes: int, now: datetime | None = None
) -> list[MinuteMetrics]:
    now = now or datetime.now(timezone.utc)
    buckets = minute_range(now, minutes)

    async with redis.pipeline(transaction=False) as pipe:
        for minute_start in buckets:
            pipe.hgetall(bucket_key(minute_start))
        raw_results = await pipe.execute()

    metrics = []
    for minute_start, raw in zip(buckets, raw_results, strict=True):
        processed = int(raw.get(b"processed", 0))
        failed = int(raw.get(b"failed", 0))
        metrics.append(MinuteMetrics(minute_start=minute_start, processed=processed, failed=failed))
    return metrics
