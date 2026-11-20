import asyncio
import logging
import random
from datetime import datetime, timezone
from uuid import uuid4

from faststream import FastStream
from sqlalchemy import select

from src.core.models.models import OutboxMessage, Payment, PaymentStatus
from src.database.database import AsyncSessionLocal
from src.messaging.rabbitmq import broker, outbox_dlq_queue, payments_new_queue

logger = logging.getLogger("payment_consumer")

app = FastStream(broker)


@app.after_startup
async def start_outbox_worker():
    from src.consumer.outbox_processor import outbox_worker

    asyncio.create_task(outbox_worker())


@broker.subscriber(payments_new_queue)
async def process_payment(message: dict):
    payment_id = message.get("payment_id")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()

        # Idempotent handling: the message may be redelivered (at-least-once),
        # skip payments that are already processed
        if not payment or payment.status != PaymentStatus.PENDING:
            return

        # Emulate payment processing (2-5 seconds, 90% success)
        await asyncio.sleep(random.uniform(2, 5))
        success = random.random() < 0.9
        new_status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED

        # Atomic update: payment status + outbox webhook event are committed
        # in ONE transaction. If the process dies mid-way, RabbitMQ redelivers
        # the message and it is handled again from scratch.
        payment.status = new_status
        payment.processed_at = datetime.now(timezone.utc)
        session.add(
            OutboxMessage(
                id=str(uuid4()),
                event_type="payment.processed",
                payload={
                    "payment_id": payment_id,
                    "status": new_status.as_string,
                    "amount": str(payment.amount),
                    "currency": payment.currency,
                    # webhook_url goes into the payload so the outbox relay
                    # does not need an extra DB lookup
                    "webhook_url": payment.webhook_url,
                },
                processed=False,
            )
        )
        await session.commit()
        logger.info("Payment %s processed -> %s", payment_id, new_status.as_string)


@broker.subscriber(outbox_dlq_queue)
async def dead_letter_handler(message: dict):
    """DLQ listener: declares the queue on startup and logs dead letters.
    Real handling (replay / alerting) is done manually."""
    logger.error("[DLQ] dead letter received: %s", message)
