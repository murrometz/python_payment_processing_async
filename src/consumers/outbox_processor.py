from faststream import Context
from faststream.rabbit import RabbitBroker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from ..database import AsyncSessionLocal
from ..models.models import OutboxMessage
from .payment_consumer import send_webhook_with_retry
import asyncio

broker = Context()

@broker.subscriber("outbox.process")
async def process_outbox(message: dict):
    async with AsyncSessionLocal() as session:
        # Get unprocessed outbox messages
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed == False)
            .order_by(OutboxMessage.created_at)
        )
        messages = result.scalars().all()
        
        for msg in messages:
            try:
                # Send webhook with retry
                success = await send_webhook_with_retry(
                    msg.payload.get("webhook_url"),  # Should be stored in payload or payment
                    msg.payload
                )
                
                if success:
                    await session.execute(
                        update(OutboxMessage)
                        .where(OutboxMessage.id == msg.id)
                        .values(processed=True)
                    )
                else:
                    # Move to DLQ after max retries
                    await broker.publish(
                        {"outbox_id": msg.id, "payload": msg.payload},
                        "outbox.dlq"
                    )
                    
            except Exception as e:
                # Log error and move to DLQ
                await broker.publish(
                    {"outbox_id": msg.id, "error": str(e), "payload": msg.payload},
                    "outbox.dlq"
                )
        
        await session.commit()