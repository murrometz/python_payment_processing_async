import os

from faststream.rabbit import RabbitBroker

RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")

# Queue names shared by the API, the consumer and the outbox worker
NEW_PAYMENT_QUEUE = "payments.new"
DLQ_QUEUE = "outbox.dlq"

# Single broker instance shared by the consumer (subscriber) and
# the outbox worker (publisher). The API no longer talks to RabbitMQ directly:
# publication happens only through the outbox table (classic outbox pattern).
broker = RabbitBroker(RABBITMQ_URL)
