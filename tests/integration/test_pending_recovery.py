import asyncio
from datetime import datetime, timezone

from src.aggregation.metrics import get_metrics
from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event


async def test_pending_entry_is_claimed_and_completed_by_another_consumer(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    event = make_event("evt-1", occurred_at=occurred_at)
    await publish_event(redis, settings, event)

    ghost = PaymentEventConsumer(redis, settings, "ghost")
    await ghost.ensure_group()
    # Simula un consumidor que lee pero muere antes de aplicar/hacer ack.
    await redis.xreadgroup(
        groupname=settings.consumer_group,
        consumername="ghost",
        streams={settings.stream_name: ">"},
        count=10,
    )

    await asyncio.sleep(settings.pending_min_idle_ms / 1000 + 0.05)

    rescuer = PaymentEventConsumer(redis, settings, "rescuer")
    stop_event = asyncio.Event()
    task = asyncio.create_task(rescuer.run(stop_event))
    await asyncio.sleep(0.3)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == 1

    pending_summary = await redis.xpending(settings.stream_name, settings.consumer_group)
    assert pending_summary["pending"] == 0
