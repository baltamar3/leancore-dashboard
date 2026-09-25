from datetime import datetime, timezone

from redis.asyncio import Redis

from src.config.settings import Settings
from src.consumer.schemas import PaymentEvent


def make_event(
    event_id: str,
    event_type: str = "payment.processed",
    occurred_at: datetime | None = None,
    payment_id: str | None = None,
) -> PaymentEvent:
    return PaymentEvent(
        event_id=event_id,
        type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        payment_id=payment_id or f"pay-{event_id}",
    )


async def publish_event(redis: Redis, settings: Settings, event: PaymentEvent) -> bytes:
    return await redis.xadd(
        settings.stream_name,
        {
            "event_id": event.event_id,
            "type": event.type.value,
            "occurred_at": event.occurred_at.isoformat(),
            "payment_id": event.payment_id,
        },
    )


async def publish_raw(redis: Redis, settings: Settings, fields: dict) -> bytes:
    return await redis.xadd(settings.stream_name, fields)
