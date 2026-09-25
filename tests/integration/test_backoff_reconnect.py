import asyncio
from datetime import datetime, timezone

from redis.exceptions import ConnectionError as RedisConnectionError

from src.aggregation.metrics import get_metrics
from src.consumer.consumer import PaymentEventConsumer
from tests.integration.helpers import make_event, publish_event


async def test_consumer_recovers_from_transient_connection_errors(redis, settings):
    occurred_at = datetime.now(timezone.utc)
    consumer = PaymentEventConsumer(redis, settings, "consumer-a")
    await consumer.ensure_group()

    real_consume_new = consumer._consume_new
    calls = {"n": 0}

    async def flaky_consume_new():
        calls["n"] += 1
        if calls["n"] <= 2:
            raise RedisConnectionError("simulated outage")
        await real_consume_new()

    consumer._consume_new = flaky_consume_new

    await publish_event(redis, settings, make_event("evt-1", occurred_at=occurred_at))

    stop_event = asyncio.Event()
    task = asyncio.create_task(consumer.run(stop_event))
    await asyncio.sleep(0.5)
    stop_event.set()
    await asyncio.wait_for(task, timeout=5)

    assert calls["n"] >= 3  # sobrevivió 2 fallos y siguió reintentando

    metrics = await get_metrics(redis, minutes=1, now=occurred_at)
    assert sum(m.processed + m.failed for m in metrics) == 1
