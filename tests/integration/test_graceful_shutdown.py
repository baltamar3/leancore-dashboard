import asyncio
from datetime import datetime, timezone

from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event


async def test_shutdown_stops_consumption_without_leaving_unacked_entries(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    for i in range(10):
        await publish_event(redis, settings, make_event(f"evt-{i}", occurred_at=occurred_at))

    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    stop_event = asyncio.Event()
    task = asyncio.create_task(consumer.run(stop_event))
    await asyncio.sleep(0.4)  # deja que procese el lote disponible

    stop_event.set()
    await asyncio.wait_for(task, timeout=2)  # debe retornar pronto, no colgarse

    pending_summary = await redis.xpending(settings.stream_name, settings.consumer_group)
    assert pending_summary["pending"] == 0
