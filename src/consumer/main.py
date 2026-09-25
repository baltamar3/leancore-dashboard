import asyncio
import logging
import os
import signal
import uuid

from src.config.settings import get_settings
from src.consumer.consumer import PaymentEventConsumer
from src.consumer.redis_client import create_redis

logger = logging.getLogger(__name__)


def _register_shutdown_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            # Windows no soporta add_signal_handler para SIGTERM; en desarrollo
            # local basta con Ctrl+C (SIGINT), que asyncio traduce a KeyboardInterrupt.
            pass


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    consumer_name = os.environ.get("CONSUMER_NAME", f"consumer-{uuid.uuid4().hex[:8]}")

    redis = create_redis(settings)
    stop_event = asyncio.Event()
    _register_shutdown_handlers(stop_event)

    consumer = PaymentEventConsumer(redis, settings, consumer_name)
    logger.info("Starting consumer %s", consumer_name)
    try:
        await consumer.run(stop_event)
    finally:
        await redis.aclose()
        logger.info("Consumer %s stopped", consumer_name)


if __name__ == "__main__":
    asyncio.run(main())
