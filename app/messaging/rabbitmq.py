from faststream import FastStream, Context
from faststream.rabbit import RabbitBroker
import os

# Connection URL is taken from environment variables
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Initialize the broker and the FastStream application
broker = RabbitBroker(RABBITMQ_URL)
app = FastStream(broker)

@broker.publisher("payments.new")
async def publish_payment_event(payment_id: str, context: Context):
    """
    Publishes a new payment event to the 'payments.new' queue.
    The 'context' is required by FastStream for internal routing.
    """
    return {"payment_id": payment_id}

# Note: The consumer for payment processing is located in a separate module (./consumer/)
# and will import this broker instance to subscribe to the queue.