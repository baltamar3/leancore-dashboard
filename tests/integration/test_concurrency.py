import asyncio
from datetime import datetime, timezone

from src.aggregation.metrics import get_metrics
from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event


async def test_concurrent_consumers_with_duplicates_produce_exact_count(redis, settings):
    """Prueba central del ejercicio: N consumidores en paralelo, con reentregas
    intencionales, deben producir un conteo exacto (sin duplicar ni perder)."""
    occurred_at = datetime.now(timezone.utc)
    unique_events = [make_event(f"evt-{i}", occurred_at=occurred_at) for i in range(30)]

    for event in unique_events:
        await publish_event(redis, settings, event)
    # Simula reentregas/reintentos del productor: mismos event_id publicados de nuevo.
    for event in unique_events[:10]:
        await publish_event(redis, settings, event)

    consumers = [PaymentEventConsumer(redis, settings, f"consumer-{i}") for i in range(3)]
    stop_event = asyncio.Event()
    tasks = [asyncio.create_task(consumer.run(stop_event)) for consumer in consumers]

    await asyncio.sleep(1.0)
    stop_event.set()
    await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    total = sum(m.processed + m.failed for m in metrics)
    assert total == len(unique_events)

    pending_summary = await redis.xpending(settings.stream_name, settings.consumer_group)
    assert pending_summary["pending"] == 0
