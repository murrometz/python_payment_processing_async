import asyncio
import logging
from datetime import datetime, timezone

import aiohttp
from sqlalchemy import select

from src.core.models.models import OutboxMessage
from src.database.database import AsyncSessionLocal
from src.messaging.rabbitmq import DLQ_QUEUE, NEW_PAYMENT_QUEUE, broker

logger = logging.getLogger("outbox_worker")

MAX_WEBHOOK_RETRIES = 3
BATCH_SIZE = 50


async def send_webhook_with_retry(url: str, payload: dict, max_retries: int = MAX_WEBHOOK_RETRIES):
    """Send the webhook with up to `max_retries` attempts and exponential backoff.
    Returns (ok, last_error)."""
    last_error = None
    async with aiohttp.ClientSession() as http:
        for attempt in range(max_retries):
            try:
                async with http.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status < 300:
                        return True, None
                    last_error = f"HTTP {response.status}"
            except Exception as exc:
                last_error = str(exc)
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # 1s, 2s, 4s backoff
    return False, last_error


async def process_outbox_batch(batch_size: int = BATCH_SIZE) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed.is_(False))  # noqa: E712
            .order_by(OutboxMessage.created_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)  # safe for multiple workers
        )
        messages = result.scalars().all()

        for msg in messages:
            try:
                if msg.event_type == "payment.new":
                    # Publish the event to RabbitMQ only now (classic outbox)
                    await broker.publish(msg.payload, NEW_PAYMENT_QUEUE)
                    logger.info("Outbox %s: published %s", msg.id, msg.event_type)
                    msg.processed = True
                    msg.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    await session.commit()

                elif msg.event_type == "payment.processed":
                    url = (msg.payload or {}).get("webhook_url")
                    if not url:
                        msg.last_error = "webhook_url is missing in payload"
                        await session.commit()
                        continue
                    ok, error = await send_webhook_with_retry(url, msg.payload)
                    if ok:
                        logger.info("Outbox %s: webhook delivered", msg.id)
                        msg.processed = True
                        msg.processed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                        msg.attempts = MAX_WEBHOOK_RETRIES
                        msg.last_error = None
                    else:
                        msg.last_error = error
                        msg.attempts = MAX_WEBHOOK_RETRIES
                        logger.error("Outbox %s: webhook failed (%s) -> DLQ", msg.id, error)
                        await broker.publish(
                            {
                                "outbox_id": msg.id,
                                "payment_id": (msg.payload or {}).get("payment_id"),
                                "error": error,
                                "payload": msg.payload,
                            },
                            DLQ_QUEUE,
                        )
                        msg.processed = True
                    await session.commit()

                else:
                    logger.warning("Outbox %s: unknown event_type %r, skipping", msg.id, msg.event_type)
                    msg.processed = True
                    msg.last_error = f"unknown event_type {msg.event_type!r}"
                    await session.commit()

            except Exception as exc:
                # infra error (e.g. RabbitMQ down): keep the record unprocessed,
                # it will be retried on the next poll
                msg.last_error = str(exc)
                msg.attempts = (msg.attempts or 0) + 1
                await session.commit()
                logger.exception("Outbox %s: delivery error, will retry", msg.id)


async def outbox_worker(poll_interval: float = 2.0):
    """Background task: polls the outbox table and ships events."""
    logger.info("Outbox worker started (poll every %ss)", poll_interval)
    await asyncio.sleep(1)  # give the broker a moment to start
    while True:
        try:
            await process_outbox_batch()
        except Exception:
            logger.exception("Outbox batch failed")
        await asyncio.sleep(poll_interval)


# Subscribing only to declare the durable DLQ queue and log dead messages
@broker.subscriber(DLQ_QUEUE, durable=True)
async def dlq_handler(message: dict):
    logger.error("[DLQ] dead message: %s", message)
