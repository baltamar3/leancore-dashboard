import asyncio
from datetime import datetime, timezone

from src.aggregation.metrics import get_metrics
from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event


async def test_ensure_group_is_idempotent(redis, settings):
    consumer = PaymentEventConsumer(redis, settings, "consumer-a")

    await consumer.ensure_group()
    await consumer.ensure_group()  # no debe lanzar BUSYGROUP

    info = await redis.xinfo_groups(settings.stream_name)
    assert len(info) == 1


async def test_single_consumer_processes_all_published_events(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    events = [make_event(f"evt-{i}", occurred_at=occurred_at) for i in range(5)]
    for event in events:
        await publish_event(redis, settings, event)

    stop_event = asyncio.Event()
    task = asyncio.create_task(consumer.run(stop_event))
    await asyncio.sleep(0.5)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == 5


async def test_two_consumers_share_load_without_duplicating_or_losing(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    events = [make_event(f"evt-{i}", occurred_at=occurred_at) for i in range(40)]
    for event in events:
        await publish_event(redis, settings, event)

    consumer_a = PaymentEventConsumer(redis, settings, "consumer-a")
    consumer_b = PaymentEventConsumer(redis, settings, "consumer-b")
    stop_event = asyncio.Event()
    tasks = [
        asyncio.create_task(consumer_a.run(stop_event)),
        asyncio.create_task(consumer_b.run(stop_event)),
    ]
    await asyncio.sleep(0.8)
    stop_event.set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == len(events)
