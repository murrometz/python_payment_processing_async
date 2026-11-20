from faststream import FastStream, Context
from faststream.rabbit import RabbitBroker
import os

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

broker = RabbitBroker(RABBITMQ_URL)
app = FastStream(broker)

@broker.publisher("payments.new")
async def publish_payment_event(payment_id: str, context: Context):
    return {"payment_id": payment_id}

# Consumer for payment processing will be in a separate file