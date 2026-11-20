from faststream import Context
from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..database import AsyncSessionLocal
from ..models.models import Payment, PaymentStatus, OutboxMessage
import asyncio
import random
import aiohttp
from uuid import uuid4
from datetime import datetime

broker = Context()

@broker.subscriber("payments.new")
async def process_payment(message: dict):
    payment_id = message.get("payment_id")
    
    async with AsyncSessionLocal() as session:
        # Get payment from database
        result = await session.execute(select(Payment).where(Payment.id == payment_id))
        payment = result.scalar_one_or_none()
        
        if not payment:
            return
        
        # Emulate payment processing (2-5 seconds, 90% success)
        await asyncio.sleep(random.uniform(2, 5))
        success = random.random() < 0.9
        
        new_status = PaymentStatus.SUCCEEDED if success else PaymentStatus.FAILED
        
        # Update payment status
        await session.execute(
            update(Payment)
            .where(Payment.id == payment_id)
            .values(status=new_status, processed_at=datetime.utcnow())
        )
        
        # Create outbox message for webhook
        outbox_id = str(uuid4())
        outbox_message = OutboxMessage(
            id=outbox_id,
            event_type="payment.processed",
            payload={
                "payment_id": payment_id,
                "status": new_status.value,
                "amount": float(payment.amount),
                "currency": payment.currency
            },
            processed=False
        )
        session.add(outbox_message)
        
        await session.commit()

# Webhook sender with retry logic
async def send_webhook_with_retry(url: str, payload: dict, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False