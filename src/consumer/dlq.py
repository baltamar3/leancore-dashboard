"""Envío de entradas inválidas o "poison" al stream de dead-letter."""

import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from src.config.settings import Settings


def _decode(value: bytes | str) -> str:
    """Decodifica un valor de Redis (bytes o str) a `str`."""
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def _decode_mapping(fields: dict[bytes | str, bytes | str]) -> dict[str, str]:
    """Decodifica todas las claves/valores de un mapeo de campos de Redis."""
    return {_decode(k): _decode(v) for k, v in fields.items()}


async def send_to_dlq(
    redis: Redis,
    settings: Settings,
    original_id: bytes | str,
    raw_payload: dict[bytes | str, bytes | str],
    error: str,
    attempts: int | None = None,
) -> None:
    """Copia una entrada al stream de dead-letter y la marca con el motivo."""
    payload: dict[str, str] = {
        "original_id": _decode(original_id),
        "raw_payload": json.dumps(_decode_mapping(raw_payload)),
        "error": error,
        "received_at": datetime.now(timezone.utc).isoformat(),
    }
    if attempts is not None:
        payload["attempts"] = str(attempts)

    await redis.xadd(settings.dlq_stream_name, payload)
