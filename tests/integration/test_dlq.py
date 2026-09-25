import asyncio
from datetime import datetime, timezone

from src.aggregation.metrics import get_metrics
from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event, publish_raw


async def _run_briefly(consumer, seconds=0.4):
    stop_event = asyncio.Event()
    task = asyncio.create_task(consumer.run(stop_event))
    await asyncio.sleep(seconds)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)


async def test_malformed_event_is_quarantined_without_affecting_counts(redis, settings):
    await publish_raw(redis, settings, {"event_id": "bad-1", "type": "payment.processed"})

    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    await _run_briefly(consumer)

    dlq_entries = await redis.xrange(settings.dlq_stream_name)
    assert len(dlq_entries) == 1

    metrics = await get_metrics(redis, minutes=1)
    assert sum(m.processed + m.failed for m in metrics) == 0


async def test_unknown_event_type_is_quarantined(redis, settings):
    await publish_raw(
        redis,
        settings,
        {
            "event_id": "evt-x",
            "type": "payment.refunded",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payment_id": "pay-x",
        },
    )

    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    await _run_briefly(consumer)

    dlq_entries = await redis.xrange(settings.dlq_stream_name)
    assert len(dlq_entries) == 1


async def test_valid_event_after_a_malformed_one_is_still_counted(redis, settings):
    """Un evento malformado no debe bloquear el resto del stream."""
    occurred_at = datetime.now(timezone.utc)
    await publish_raw(redis, settings, {"event_id": "bad-1", "type": "payment.processed"})
    await publish_event(redis, settings, make_event("evt-ok", occurred_at=occurred_at))

    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    await _run_briefly(consumer)

    dlq_entries = await redis.xrange(settings.dlq_stream_name)
    assert len(dlq_entries) == 1

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == 1


async def test_poison_message_is_quarantined_after_max_delivery_attempts(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    event = make_event("evt-poison", occurred_at=occurred_at)
    await publish_event(redis, settings, event)

    ghost = PaymentEventConsumer(redis, settings, "ghost")
    await ghost.ensure_group()
    response = await redis.xreadgroup(
        groupname=settings.consumer_group,
        consumername="ghost",
        streams={settings.stream_name: ">"},
        count=10,
    )
    entry_id, _ = response[0][1][0]

    for _ in range(settings.max_delivery_attempts + 1):
        await redis.xclaim(
            settings.stream_name,
            settings.consumer_group,
            "ghost",
            min_idle_time=0,
            message_ids=[entry_id],
        )

    await asyncio.sleep(settings.pending_min_idle_ms / 1000 + 0.05)

    rescuer = PaymentEventConsumer(redis, settings, "rescuer")
    await rescuer._recover_pending()

    dlq_entries = await redis.xrange(settings.dlq_stream_name)
    assert len(dlq_entries) == 1
    assert b"max_delivery_attempts_exceeded" in dlq_entries[0][1][b"error"]

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == 0

    pending_summary = await redis.xpending(settings.stream_name, settings.consumer_group)
    assert pending_summary["pending"] == 0
