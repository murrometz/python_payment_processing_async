import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import uuid4

from faststream import FastStream
from sqlalchemy import select, update

from src.consumer.outbox_processor import outbox_worker
from src.core.models.models import OutboxMessage, Payment, PaymentStatus
from src.database.database import AsyncSessionLocal
from src.messaging.rabbitmq import DLQ_QUEUE, NEW_PAYMENT_QUEUE, broker

logger = logging.getLogger("payment_consumer")

MAX_PROCESS_RETRIES = 3

app = FastStream(broker)


@app.after_startup
async def start_outbox_worker():
    asyncio.create_task(outbox_worker())


async def _process(payment_id: str) -> None:
    """Process the payment and, in the SAME transaction, write the outbox
    record for the webhook event (classic outbox pattern)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if payment is None:
            logger.warning("Payment %s not found, dropping message", payment_id)
            return

        # Idempotency on the consumer side: skip redeliveries of processed payments
        if payment.status is not PaymentStatus.PENDING:
            logger.info("Payment %s already processed, skipping", payment_id)
            return

        # Emulate payment processing (2-5 seconds, 90% success)
        await asyncio.sleep(random.uniform(2, 5))
        success = random.random() < 0.9
        new_status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED

        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(
                status=new_status,
                processed_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
        )

        session.add(
            OutboxMessage(
                event_type="payment.processed",
                payload={
                    "event": "payment.processed",
                    "payment_id": payment_id,
                    "status": new_status.value,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    "webhook_url": payment.webhook_url,
                },
            )
        )
        # One commit: payment status update + outbox record are atomic
        await session.commit()
        logger.info("Payment %s processed -> %s", payment_id, new_status.value)


@broker.subscriber(NEW_PAYMENT_QUEUE, durable=True)
async def process_payment(message: dict):
    payment_id = message.get("payment_id")
    attempt = int(message.get("attempt", 0))

    try:
        await _process(payment_id)
    except Exception as exc:
        logger.exception("Processing failed for %s (attempt %d)", payment_id, attempt + 1)
        if attempt + 1 >= MAX_PROCESS_RETRIES:
            # 3 failed attempts -> Dead Letter Queue
            await broker.publish(
                {
                    "outbox_id": None,
                    "payment_id": payment_id,
                    "error": str(exc),
                    "payload": message,
                },
                DLQ_QUEUE,
            )
        else:
            # Requeue with the attempt counter for exponential-style retries
            await broker.publish({**message, "attempt": attempt + 1}, NEW_PAYMENT_QUEUE)
