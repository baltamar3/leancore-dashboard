"""Consumer for `settings.stream_name`: dedupe, aggregation, DLQ, recovery."""

import asyncio
import logging

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from src.aggregation.dedupe import DedupeAggregator
from src.config.settings import Settings
from src.consumer.dlq import send_to_dlq
from src.consumer.schemas import PaymentEvent

logger = logging.getLogger(__name__)

# A Redis Stream entry is (id, fields); both arrive as bytes by default.
StreamEntryId = bytes
StreamFields = dict[bytes, bytes]
StreamEntry = tuple[StreamEntryId, StreamFields]


def _decode_fields(fields: StreamFields) -> dict[str, str]:
    """Decode a stream entry's keys and values to `str`."""
    return {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in fields.items()
    }


class PaymentEventConsumer:
    """Consumes `settings.stream_name` with pending recovery, dead-lettering,
    and backoff reconnection (see specs `payment-event-ingestion` and ADR 002/003)."""

    def __init__(self, redis: Redis, settings: Settings, consumer_name: str) -> None:
        """Store the dependencies; does not touch Redis until `run()`/`ensure_group()`."""
        self._redis: Redis = redis
        self._settings: Settings = settings
        self._consumer_name: str = consumer_name
        self._aggregator: DedupeAggregator = DedupeAggregator(redis, settings)

    async def ensure_group(self) -> None:
        """Create the stream and consumer group if they don't exist (idempotent)."""
        try:
            await self._redis.xgroup_create(
                self._settings.stream_name,
                self._settings.consumer_group,
                id="0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def run(self, stop_event: asyncio.Event) -> None:
        """Main loop: recovers pending entries, consumes new ones, retries with
        backoff if Redis is unreachable, and stops once `stop_event` is set."""
        backoff: float = self._settings.reconnect_backoff_initial_seconds
        while not stop_event.is_set():
            try:
                await self.ensure_group()
                await self._recover_pending()
                if stop_event.is_set():
                    break
                await self._consume_new()
                backoff = self._settings.reconnect_backoff_initial_seconds
            except (RedisConnectionError, ConnectionRefusedError, TimeoutError):
                logger.warning("Redis unreachable, retrying in %.1fs", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, self._settings.reconnect_backoff_max_seconds)

    async def _recover_pending(self) -> None:
        """Claim idle pending entries; send "poison" ones to the DLQ."""
        pending: list[dict] = await self._redis.xpending_range(
            self._settings.stream_name,
            self._settings.consumer_group,
            min="-",
            max="+",
            count=self._settings.consumer_batch_size,
            idle=self._settings.pending_min_idle_ms,
        )
        if not pending:
            return

        poison_ids: list[StreamEntryId] = [
            entry["message_id"]
            for entry in pending
            if entry["times_delivered"] > self._settings.max_delivery_attempts
        ]
        recoverable_ids: list[StreamEntryId] = [
            entry["message_id"]
            for entry in pending
            if entry["times_delivered"] <= self._settings.max_delivery_attempts
        ]

        for entry_id in poison_ids:
            await self._quarantine_by_id(entry_id, reason="max_delivery_attempts_exceeded")

        if recoverable_ids:
            claimed: list[StreamEntry] = await self._redis.xclaim(
                self._settings.stream_name,
                self._settings.consumer_group,
                self._consumer_name,
                min_idle_time=self._settings.pending_min_idle_ms,
                message_ids=recoverable_ids,
            )
            await self._process_entries(claimed)

    async def _consume_new(self) -> None:
        """Read new entries from the stream (blocking up to `consumer_block_ms`)."""
        response = await self._redis.xreadgroup(
            groupname=self._settings.consumer_group,
            consumername=self._consumer_name,
            streams={self._settings.stream_name: ">"},
            count=self._settings.consumer_batch_size,
            block=self._settings.consumer_block_ms,
        )
        if not response:
            return
        _, entries = response[0]
        await self._process_entries(entries)

    async def _process_entries(self, entries: list[StreamEntry]) -> None:
        """Process each entry in the list, one at a time, in order."""
        for entry_id, fields in entries:
            await self._process_one(entry_id, fields)

    async def _process_one(self, entry_id: StreamEntryId, fields: StreamFields) -> None:
        """Validate, apply (dedupe+aggregation) and ack an entry, or send it
        to the DLQ if it fails validation. Ack always happens after apply."""
        try:
            event: PaymentEvent = PaymentEvent.model_validate(_decode_fields(fields))
        except ValidationError as exc:
            await send_to_dlq(
                self._redis,
                self._settings,
                original_id=entry_id,
                raw_payload=fields,
                error=str(exc),
            )
            await self._ack(entry_id)
            return

        await self._aggregator.apply(event)
        await self._ack(entry_id)

    async def _quarantine_by_id(self, entry_id: StreamEntryId, reason: str) -> None:
        """Copy the `entry_id` entry to the DLQ (by id, its fields not in hand) and ack it."""
        raw: list[StreamEntry] = await self._redis.xrange(
            self._settings.stream_name, min=entry_id, max=entry_id
        )
        fields: StreamFields = raw[0][1] if raw else {}
        await send_to_dlq(
            self._redis, self._settings, original_id=entry_id, raw_payload=fields, error=reason
        )
        await self._ack(entry_id)

    async def _ack(self, entry_id: StreamEntryId) -> None:
        """Acknowledge (`XACK`) an entry that was already applied."""
        await self._redis.xack(self._settings.stream_name, self._settings.consumer_group, entry_id)
