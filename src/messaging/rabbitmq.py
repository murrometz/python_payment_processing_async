import os

from faststream import FastStream, Context
from faststream.rabbit import RabbitBroker

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Single broker instance shared by the API (publisher) and consumer (subscriber)
broker = RabbitBroker(RABBITMQ_URL)
app = FastStream(broker)

@broker.publisher("payments.new")
async def publish_payment_event(event: dict) -> None:
    """Publishes a new payment event to the 'payments.new' queue."""
    await broker.publish(event, queue="payments.processing")
