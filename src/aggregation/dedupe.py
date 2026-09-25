"""Dedupe atómico por `event_id` + agregación por minuto sobre Redis (ADR 002)."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from redis.asyncio import Redis
from redis.commands.core import AsyncScript

from src.aggregation.buckets import bucket_key, classify_event
from src.config.settings import Settings
from src.consumer.schemas import PaymentEvent, PaymentEventType

_LUA_SCRIPT_PATH: Path = Path(__file__).parent / "lua" / "dedupe_and_count.lua"

_FIELD_BY_TYPE: dict[PaymentEventType, str] = {
    PaymentEventType.PROCESSED: "processed",
    PaymentEventType.FAILED: "failed",
}


@dataclass(frozen=True)
class ApplyResult:
    """Resultado de aplicar un evento: si se contó y a qué bucket, con qué marcas."""

    applied: bool
    bucket_key: str
    out_of_window: bool
    fallback: bool


class DedupeAggregator:
    """Aplica dedupe atómico + agregación por minuto (ADR 002, 003, 005)."""

    def __init__(self, redis: Redis, settings: Settings) -> None:
        """Registra el script Lua de dedupe+incremento contra `redis`."""
        self._redis: Redis = redis
        self._settings: Settings = settings
        self._script: AsyncScript = redis.register_script(
            _LUA_SCRIPT_PATH.read_text(encoding="utf-8")
        )

    async def apply(self, event: PaymentEvent, now: datetime | None = None) -> ApplyResult:
        """Deduplica y agrega `event`; es un no-op si su `event_id` ya fue aplicado."""
        now = now or datetime.now(timezone.utc)
        placement = classify_event(
            occurred_at=event.occurred_at,
            now=now,
            allowed_lateness_seconds=self._settings.allowed_lateness_seconds,
            bucket_retention_seconds=self._settings.bucket_retention_seconds,
        )
        bucket: str = bucket_key(placement.bucket_start)
        dedupe_key: str = f"dedupe:payments:{event.event_id}"

        applied: int = await self._script(
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
