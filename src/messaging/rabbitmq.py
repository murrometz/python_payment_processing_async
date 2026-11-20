import os

from faststream import FastStream
from faststream.rabbit import RabbitBroker, RabbitQueue

from src.config.config import settings

# Single broker instance shared by the consumer (subscriber) and the outbox relay (publisher)
broker = RabbitBroker(settings.rabbitmq_url)
app = FastStream(broker)

# Durable queue objects: FastStream declares them on startup.
# Queue properties (durable) must match on every declare, otherwise RabbitMQ
# raises PRECONDITION_FAILED - always use these objects, not bare strings,
# for subscribers and publishers.
payments_new_queue = RabbitQueue("payments.new", durable=True)
outbox_dlq_queue = RabbitQueue("outbox.dlq", durable=True)
