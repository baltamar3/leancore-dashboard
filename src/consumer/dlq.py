import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from src.config.settings import Settings


def _decode(value) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _decode_mapping(fields: dict) -> dict:
    return {_decode(k): _decode(v) for k, v in fields.items()}


async def send_to_dlq(
    redis: Redis,
    settings: Settings,
    original_id,
    raw_payload: dict,
    error: str,
    attempts: int | None = None,
) -> None:
    payload = {
        "original_id": _decode(original_id),
        "raw_payload": json.dumps(_decode_mapping(raw_payload)),
        "error": error,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if attempts is not None:
        payload["attempts"] = str(attempts)

    await redis.xadd(settings.dlq_stream_name, payload)
