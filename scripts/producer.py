#!/usr/bin/env python
"""Payment event generator to demonstrate dedupe, out-of-order events, and DLQ.

Examples:
  python scripts/producer.py --count 200
  python scripts/producer.py --count 200 --duplicate-rate 0.2 --out-of-order --spread-seconds 120
  python scripts/producer.py --count 50 --malformed-rate 0.1
"""

import argparse
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from redis import Redis

from src.config.settings import Settings, get_settings


def build_valid_fields(event_type: str, occurred_at: datetime) -> dict[str, str]:
    """Build the fields of a valid payment event to publish on the stream."""
    return {
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "payment_id": f"pay-{uuid.uuid4().hex[:8]}",
    }


def build_malformed_fields() -> dict[str, str]:
    """Pick at random one of the invalid-event variants (missing field,
    unknown type, badly-formatted date)."""
    variants: list[dict[str, str]] = [
        {"event_id": str(uuid.uuid4()), "type": "payment.processed"},
        {
            "event_id": str(uuid.uuid4()),
            "type": "payment.refunded",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "payment_id": "pay-unknown-type",
        },
        {
            "event_id": str(uuid.uuid4()),
            "type": "payment.processed",
            "occurred_at": "not-a-date",
            "payment_id": "pay-bad-date",
        },
    ]
    return random.choice(variants)


def build_batch(args: argparse.Namespace, now: datetime) -> list[tuple[dict[str, str], bool]]:
    """Return (fields, is_malformed) pairs."""
    batch: list[tuple[dict[str, str], bool]] = []
    for _ in range(args.count):
        occurred_at: datetime = now
        if args.spread_seconds:
            occurred_at = now - timedelta(seconds=random.uniform(0, args.spread_seconds))

        if random.random() < args.malformed_rate:
            batch.append((build_malformed_fields(), True))
        else:
            is_failed: bool = random.random() < args.failed_rate
            event_type: str = "payment.failed" if is_failed else "payment.processed"
            batch.append((build_valid_fields(event_type, occurred_at), False))

    if args.out_of_order:
        random.shuffle(batch)

    return batch


def main() -> None:
    """CLI: publish a batch of payment events according to the given flags."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Generador de eventos de pago para pruebas"
    )
    parser.add_argument("--count", type=int, default=100, help="Cantidad de eventos base")
    parser.add_argument(
        "--duplicate-rate", type=float, default=0.0, help="Prob. (0-1) de republicar un evento"
    )
    parser.add_argument(
        "--malformed-rate", type=float, default=0.0, help="Prob. (0-1) de evento inválido"
    )
    parser.add_argument("--failed-rate", type=float, default=0.2, help="Proporción payment.failed")
    parser.add_argument(
        "--out-of-order", action="store_true", help="Publica en orden distinto al de occurred_at"
    )
    parser.add_argument(
        "--spread-seconds",
        type=int,
        default=0,
        help="Distribuye occurred_at en los últimos N segundos (simula tardíos)",
    )
    parser.add_argument("--delay-ms", type=int, default=0, help="Pausa entre publicaciones (ms)")
    args: argparse.Namespace = parser.parse_args()

    settings: Settings = get_settings()
    redis: Redis = Redis.from_url(settings.redis_url)

    now: datetime = datetime.now(timezone.utc)
    batch: list[tuple[dict[str, str], bool]] = build_batch(args, now)

    published: int = 0
    duplicated: int = 0
    malformed_unique: int = sum(1 for _, is_malformed in batch if is_malformed)
    valid_unique: int = len(batch) - malformed_unique

    for fields, _ in batch:
        redis.xadd(settings.stream_name, fields)
        published += 1
        if random.random() < args.duplicate_rate:
            redis.xadd(settings.stream_name, fields)  # mismo event_id: duplicado intencional
            published += 1
            duplicated += 1
        if args.delay_ms:
            time.sleep(args.delay_ms / 1000)

    print(
        f"Publicadas {published} entradas en '{settings.stream_name}' "
        f"({len(batch)} base + {duplicated} duplicados).\n"
        f"Esperado en el tablero: {valid_unique} eventos válidos únicos "
        f"({malformed_unique} inválidos -> deberían caer en '{settings.dlq_stream_name}')."
    )


if __name__ == "__main__":
    main()
