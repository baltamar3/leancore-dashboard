from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from redis.asyncio import Redis

from src.aggregation.buckets import bucket_key, classify_event
from src.config.settings import Settings
from src.consumer.schemas import PaymentEvent, PaymentEventType

_LUA_SCRIPT_PATH = Path(__file__).parent / "lua" / "dedupe_and_count.lua"

_FIELD_BY_TYPE = {
    PaymentEventType.PROCESSED: "processed",
    PaymentEventType.FAILED: "failed",
}


@dataclass(frozen=True)
class ApplyResult:
    applied: bool
    bucket_key: str
    out_of_window: bool
    fallback: bool


class DedupeAggregator:
    """Aplica dedupe atómico + agregación por minuto (ADR 002, 003, 005)."""

    def __init__(self, redis: Redis, settings: Settings):
        self._redis = redis
        self._settings = settings
        self._script = redis.register_script(_LUA_SCRIPT_PATH.read_text(encoding="utf-8"))

    async def apply(self, event: PaymentEvent, now: datetime | None = None) -> ApplyResult:
        now = now or datetime.now(timezone.utc)
        placement = classify_event(
            occurred_at=event.occurred_at,
            now=now,
            allowed_lateness_seconds=self._settings.allowed_lateness_seconds,
            bucket_retention_seconds=self._settings.bucket_retention_seconds,
        )
        bucket = bucket_key(placement.bucket_start)
        dedupe_key = f"dedupe:payments:{event.event_id}"

        applied = await self._script(
            keys=[dedupe_key, bucket],
            args=[
                str(self._settings.dedupe_ttl_seconds),
                _FIELD_BY_TYPE[event.type],
                str(self._settings.bucket_retention_seconds),
            ],
        )

        return ApplyResult(
            applied=bool(applied),
            bucket_key=bucket,
            out_of_window=placement.out_of_window,
            fallback=placement.fallback,
        )
