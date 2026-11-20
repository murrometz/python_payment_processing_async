import asyncio
import logging

import aiohttp
from sqlalchemy import select, update

from src.core.models.models import OutboxMessage
from src.database.database import AsyncSessionLocal
from src.messaging.rabbitmq import broker, outbox_dlq_queue, payments_new_queue
from src.config.config import settings

logger = logging.getLogger("outbox_worker")


async def _post_webhook(url: str, payload: dict) -> int | None:
    """Single HTTP attempt. Returns the status code or None on a network error."""
    try:
        timeout = aiohttp.ClientTimeout(total=settings.webhook_timeout)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            async with http.post(url, json=payload) as response:
                return response.status
    except Exception as exc:
        logger.warning("Webhook attempt failed: %s", exc)
        return None


async def send_webhook_with_retry(url: str, payload: dict, max_retries: int | None = None):
    """Deliver a webhook with up to max_retries attempts (1s/2s/4s backoff).

    Returns (delivered, last_error):
      2xx/3xx  -> delivered
      4xx      -> permanent failure: the receiver rejected the notification,
                  retrying would only repeat the same answer
      5xx/net  -> transient failure, retried with backoff
    """

    max_retries = max_retries or settings.outbox_max_attempts
    last_error = None
    for attempt in range(max_retries):
        status_code = await _post_webhook(url, payload)
        if status_code is not None and status_code < 400:
            return True, None
        if status_code is not None and status_code < 500:
            return False, f"HTTP {status_code} (permanent, not retried)"
        last_error = f"HTTP {status_code}" if status_code is not None else "network error"
        if attempt < max_retries - 1:
            await asyncio.sleep(2 ** attempt)
    return False, last_error


async def _mark(session, outbox_id: str, **values) -> None:
    await session.execute(
        update(OutboxMessage).where(OutboxMessage.id == outbox_id).values(**values)
    )


async def _to_dlq(session, msg: OutboxMessage, error: str) -> None:
    """Publish to the DLQ and close the record. If the broker is down the
    publish raises, the record stays unprocessed and is retried later."""
    await broker.publish(
        {"outbox_id": msg.id, "error": error, "payload": msg.payload},
        queue=outbox_dlq_queue,
    )
    await _mark(session, msg.id, processed=True, last_error=error)


async def process_outbox_batch():
    """One polling pass. FOR UPDATE SKIP LOCKED makes it safe to run several
    relay workers against the same table."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed == False)  # noqa: E712
            .order_by(OutboxMessage.created_at)
            .limit(settings.outbox_batch_size)
            .with_for_update(skip_locked=True)
        )
        messages = result.scalars().all()

        for msg in messages:
            try:
                if msg.event_type == "payment.new":
                    # Relay: publish the event to RabbitMQ, then mark processed.
                    # The record stays unprocessed until the broker confirms.
                    await broker.publish(msg.payload, queue=payments_new_queue)
                    await _mark(session, msg.id, processed=True)

                elif msg.event_type == "payment.processed":
                    webhook_url = msg.payload.get("webhook_url")
                    if not webhook_url:
                        await _mark(
                            session, msg.id,
                            processed=True,
                            last_error="webhook_url is missing in payload",
                        )
                    else:
                        delivered, error = await send_webhook_with_retry(webhook_url, msg.payload)
                        if delivered:
                            await _mark(session, msg.id, processed=True)
                        else:
                            # All attempts failed: move to DLQ, close the record.
                            # Retry is possible only manually (set processed=False).
                            await _to_dlq(session, msg, error)
                else:
                    # Unknown event type: mark processed so it does not spin forever
                    await _mark(
                        session, msg.id,
                        processed=True,
                        last_error=f"unknown event_type: {msg.event_type}",
                    )

            except Exception:
                # Infra error (broker down, network, etc.): keep the record
                # unprocessed so it is retried on the next pass. After
                # MAX_DELIVERY_ATTEMPTS failed passes it goes to the DLQ.
                attempts = (msg.attempts or 0) + 1
                logger.exception("Outbox %s: delivery error, attempt %d", msg.id, attempts)
                if attempts >= MAX_DELIVERY_ATTEMPTS:
                    try:
                        await _to_dlq(session, msg, f"repeated infra errors, last: {attempts} attempts")
                    except Exception:
                        # DLQ publish failed too (broker is down): keep retrying
                        await _mark(session, msg.id, attempts=attempts)
                else:
                    await _mark(session, msg.id, attempts=attempts)

        await session.commit()


async def outbox_worker():
    """Background task: polls the outbox table. For 'payment.new' records it
    publishes events to RabbitMQ; for 'payment.processed' it delivers webhooks."""
    await asyncio.sleep(2)  # give the broker a moment to finish connecting
    logger.info("Outbox worker started (poll every %ss)", settings.outbox_poll_interval)
    while True:
        try:
            await process_outbox_batch()
        except Exception:
            logger.exception("Outbox batch failed")
        await asyncio.sleep(settings.outbox_poll_interval)


@broker.subscriber(outbox_dlq_queue)
async def dlq_handler(message: dict):
    logger.error("[DLQ] dead message: %s", message)
