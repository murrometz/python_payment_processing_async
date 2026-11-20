import asyncio

import aiohttp
from sqlalchemy import select, update

from src.database.database import AsyncSessionLocal
from src.core.models.models import OutboxMessage
from src.messaging.rabbitmq import broker


# Webhook sender with retry logic
async def send_webhook_with_retry(url: str, payload: dict, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        return True
        except Exception:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return False


async def process_outbox_batch():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OutboxMessage)
            .where(OutboxMessage.processed == False)  # noqa: E712
            .order_by(OutboxMessage.created_at)
        )
        messages = result.scalars().all()

        for msg in messages:
            try:
                success = await send_webhook_with_retry(
                    msg.payload.get("webhook_url"),
                    msg.payload,
                )
                if success:
                    await session.execute(
                        update(OutboxMessage).where(OutboxMessage.id == msg.id).values(processed=True)
                    )
                else:
                    # Move to DLQ so the message is not retried forever
                    await broker.publish(
                        {"outbox_id": msg.id, "error": "webhook not delivered", "payload": msg.payload},
                        "outbox.dlq",
                    )
                    await session.execute(
                        update(OutboxMessage).where(OutboxMessage.id == msg.id).values(processed=True)
                    )
            except Exception as e:
                await broker.publish(
                    {"outbox_id": msg.id, "error": str(e), "payload": msg.payload},
                    "outbox.dlq",
                )
                await session.execute(
                    update(OutboxMessage).where(OutboxMessage.id == msg.id).values(processed=True)
                )

        await session.commit()


async def outbox_worker(poll_interval: int = 5):
    """Background task: polls the outbox table and delivers webhooks."""
    await asyncio.sleep(2)  # give the consumer a moment to start
    while True:
        try:
            await process_outbox_batch()
        except Exception as e:
            print(f"[outbox-worker] error: {e}")
        await asyncio.sleep(poll_interval)
