from datetime import datetime, timezone

import fakeredis
import pytest

from src.aggregation.buckets import bucket_key, truncate_to_minute
from src.aggregation.dedupe import DedupeAggregator
from src.config.settings import Settings
from src.consumer.schemas import PaymentEvent


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis()


@pytest.fixture
def settings():
    return Settings(_env_file=None)


def make_event(
    event_id: str,
    event_type: str = "payment.processed",
    occurred_at: datetime | None = None,
):
    return PaymentEvent(
        event_id=event_id,
        type=event_type,
        occurred_at=occurred_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        payment_id="pay-1",
    )


async def test_first_application_increments_bucket(redis, settings):
    aggregator = DedupeAggregator(redis, settings)
    event = make_event("evt-1")

    result = await aggregator.apply(event, now=event.occurred_at)

    assert result.applied is True
    raw = await redis.hgetall(bucket_key(truncate_to_minute(event.occurred_at)))
    assert raw == {b"processed": b"1"}


async def test_duplicate_event_id_does_not_increment_again(redis, settings):
    aggregator = DedupeAggregator(redis, settings)
    event = make_event("evt-1")

    first = await aggregator.apply(event, now=event.occurred_at)
    second = await aggregator.apply(event, now=event.occurred_at)

    assert first.applied is True
    assert second.applied is False
    raw = await redis.hgetall(bucket_key(truncate_to_minute(event.occurred_at)))
    assert raw == {b"processed": b"1"}


async def test_two_different_events_both_count(redis, settings):
    aggregator = DedupeAggregator(redis, settings)
    processed = make_event("evt-1", "payment.processed")
    failed = make_event("evt-2", "payment.failed", occurred_at=processed.occurred_at)

    await aggregator.apply(processed, now=processed.occurred_at)
    await aggregator.apply(failed, now=failed.occurred_at)

    raw = await redis.hgetall(bucket_key(truncate_to_minute(processed.occurred_at)))
    assert raw == {b"processed": b"1", b"failed": b"1"}


async def test_retried_publication_with_same_event_id_is_deduped(redis, settings):
    """Un productor que reintenta la publicación reutiliza el mismo event_id."""
    aggregator = DedupeAggregator(redis, settings)
    event = make_event("evt-retry")

    await aggregator.apply(event, now=event.occurred_at)
    result = await aggregator.apply(event, now=event.occurred_at)

    assert result.applied is False
