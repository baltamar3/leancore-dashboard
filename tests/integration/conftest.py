import uuid

import pytest_asyncio
from redis.asyncio import Redis

from src.config.settings import Settings

TEST_REDIS_URL = "redis://localhost:6379/15"


@pytest_asyncio.fixture
async def redis():
    client = Redis.from_url(TEST_REDIS_URL)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest_asyncio.fixture
async def settings():
    unique = uuid.uuid4().hex[:8]
    return Settings(
        _env_file=None,
        redis_url=TEST_REDIS_URL,
        stream_name=f"test:stream:{unique}",
        consumer_group=f"test:group:{unique}",
        dlq_stream_name=f"test:dlq:{unique}",
        pending_min_idle_ms=50,
        max_delivery_attempts=2,
        consumer_block_ms=200,
        consumer_batch_size=20,
        reconnect_backoff_initial_seconds=0.01,
        reconnect_backoff_max_seconds=0.05,
    )
