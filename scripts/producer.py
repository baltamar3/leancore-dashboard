#!/usr/bin/env python
"""Generador de eventos de pago para demostrar dedupe, desorden y DLQ.

Ejemplos:
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

from src.config.settings import get_settings


def build_valid_fields(event_type: str, occurred_at: datetime) -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "type": event_type,
        "occurred_at": occurred_at.isoformat(),
        "payment_id": f"pay-{uuid.uuid4().hex[:8]}",
    }


def build_malformed_fields() -> dict:
    variants = [
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


def build_batch(args, now: datetime) -> list[dict]:
    batch = []
    for _ in range(args.count):
        occurred_at = now
        if args.spread_seconds:
            occurred_at = now - timedelta(seconds=random.uniform(0, args.spread_seconds))

        if random.random() < args.malformed_rate:
            fields = build_malformed_fields()
        else:
            is_failed = random.random() < args.failed_rate
            event_type = "payment.failed" if is_failed else "payment.processed"
            fields = build_valid_fields(event_type, occurred_at)

        batch.append(fields)

    if args.out_of_order:
        random.shuffle(batch)

    return batch


def main() -> None:
    parser = argparse.ArgumentParser(description="Generador de eventos de pago para pruebas")
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
    args = parser.parse_args()

    settings = get_settings()
    redis = Redis.from_url(settings.redis_url)

    now = datetime.now(timezone.utc)
    batch = build_batch(args, now)

    published = 0
    for fields in batch:
        redis.xadd(settings.stream_name, fields)
        published += 1
        if random.random() < args.duplicate_rate:
            redis.xadd(settings.stream_name, fields)  # mismo event_id: duplicado intencional
            published += 1
        if args.delay_ms:
            time.sleep(args.delay_ms / 1000)

    print(f"Publicadas {published} entradas en '{settings.stream_name}' (incluye duplicados).")


if __name__ == "__main__":
    main()
