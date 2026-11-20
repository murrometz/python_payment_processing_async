import os

from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitQueue

RABBITMQ_URL = os.getenv("RABBITMQ_URL")
if not RABBITMQ_URL:
    raise RuntimeError("RABBITMQ_URL is not set - define it in .env (see .env.example)")

# Single broker instance shared by the consumer (subscriber) and the outbox relay (publisher)
broker = RabbitBroker(RABBITMQ_URL)
app = FastStream(broker)

# Durable queue objects: FastStream declares them on startup.
# Queue properties (durable) must match on every declare, otherwise RabbitMQ
# raises PRECONDITION_FAILED - always use these objects, not bare strings,
# for subscribers and publishers.
payments_new_queue = RabbitQueue("payments.new", durable=True)
outbox_dlq_queue = RabbitQueue("outbox.dlq", durable=True)
