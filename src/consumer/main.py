"""Punto de entrada del proceso consumidor (`python -m src.consumer.main`)."""

import asyncio
import logging
import os
import signal
import uuid

from redis.asyncio import Redis

from src.config.settings import Settings, get_settings
from src.consumer.consumer import PaymentEventConsumer
from src.consumer.redis_client import create_redis

logger = logging.getLogger(__name__)


def _register_shutdown_handlers(stop_event: asyncio.Event) -> None:
    """Conecta SIGTERM/SIGINT a `stop_event.set` para el cierre ordenado."""
    loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows no soporta add_signal_handler para SIGTERM; en desarrollo
            # local basta con Ctrl+C (SIGINT), que asyncio traduce a KeyboardInterrupt.
            pass


async def main() -> None:
    """Arranca un consumidor y lo corre hasta recibir una señal de apagado."""
    logging.basicConfig(level=logging.INFO)
    settings: Settings = get_settings()
    consumer_name: str = os.environ.get("CONSUMER_NAME", f"consumer-{uuid.uuid4().hex[:8]}")

    redis: Redis = create_redis(settings)
    stop_event: asyncio.Event = asyncio.Event()
    _register_shutdown_handlers(stop_event)

    consumer: PaymentEventConsumer = PaymentEventConsumer(redis, settings, consumer_name)
    logger.info("Starting consumer %s", consumer_name)
    try:
        await consumer.run(stop_event)
    finally:
        await redis.aclose()
        logger.info("Consumer %s stopped", consumer_name)


if __name__ == "__main__":
    asyncio.run(main())
