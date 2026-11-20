from faststream import FastStream
from sqlalchemy import select, update
import asyncio
import random
from uuid import uuid4
from datetime import datetime

from src.messaging.rabbitmq import broker
from src.database.database import AsyncSessionLocal
from src.core.models.models import Payment, OutboxMessage
from src.consumer.outbox_processor import outbox_worker

app = FastStream(broker)

@app.after_startup
async def start_outbox_worker():
    asyncio.create_task(outbox_worker())

@broker.subscriber("payments.new")
async def process_payment(message: dict):
    payment_id = message.get("payment_id")

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        if not payment:
            return

        # Emulate payment processing (2-5 seconds, 90% success)
        await asyncio.sleep(random.uniform(2, 5))
        success = random.random() < 0.9
        new_status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED

        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status=new_status, processed_at=datetime.utcnow())
        )

        # Create outbox message for webhook (webhook_url is stored in the payload
        # so the outbox worker does not need an extra DB lookup)
        session.add(
            OutboxMessage(
                id=str(uuid4()),
                event_type="payment.processed",
                payload={
                    "payment_id": payment_id,
                    "status": new_status.value,
                    "amount": float(payment.amount),
                    "currency": payment.currency,
                    "webhook_url": payment.webhook_url,
                },
                processed=False,
            )
        )
        await session.commit()
