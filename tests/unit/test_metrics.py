from datetime import datetime, timezone

import fakeredis
import pytest

from src.aggregation.buckets import bucket_key
from src.aggregation.metrics import get_metrics


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis()


async def test_get_metrics_fills_missing_minutes_with_zero(redis):
    now = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    populated_minute = datetime(2026, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
    await redis.hset(bucket_key(populated_minute), mapping={"processed": 3, "failed": 1})

    metrics = await get_metrics(redis, minutes=3, now=now)

    assert [m.minute_start for m in metrics] == [
        datetime(2026, 1, 1, 12, 3, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 12, 4, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 12, 5, tzinfo=timezone.utc),
    ]
    assert metrics[0].processed == 0 and metrics[0].failed == 0
    assert metrics[1].processed == 0 and metrics[1].failed == 0
    assert metrics[2].processed == 3 and metrics[2].failed == 1
