# Payment Processing Service

Async payment processing microservice built with FastAPI, RabbitMQ (FastStream), and PostgreSQL.

## Setup

1. Copy the environment file:
```bash
cp .env.example .env
```

2. Generate the lock file and start:
```bash
poetry lock
docker compose up --build
```

Services will be available at:

- API: http://localhost:8000
- RabbitMQ Management: http://localhost:15672 (guest/guest)
- PostgreSQL: localhost:5432

## API Usage

Create Payment
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_static_api_key_here" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": 100.50,
    "currency": "USD",
    "description": "Test payment",
    "webhook_url": "https://webhook.site/your-uuid"
  }'
```

Get Payment
```bash
curl -X GET http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: your_static_api_key_here"
```

## Architecture

```
1. API (one transaction):
   INSERT payment (pending) + INSERT outbox (payment.new)

2. Outbox relay (polls the outbox table every 2s):
   sees payment.new -> publishes to RabbitMQ queue "payments.new" -> marks processed

3. Consumer (subscribed to payments.new):
   emulates gateway (2-5s, 90% success) -> ONE transaction:
   UPDATE payment status + INSERT outbox (payment.processed with webhook_url)

4. Outbox relay:
   sees payment.processed -> POST to webhook_url with 3 retries (1s, 2s, 4s)
   success -> marked processed
   all attempts failed -> message to "outbox.dlq", record closed with last_error
```

### Outbox Pattern
The API never publishes to RabbitMQ directly. Events are written to the
`outbox` table in the same transaction as business data, so a commit either
applies together with its event or not at all. The relay worker publishes
from the table, which guarantees at-least-once delivery.

### Idempotency
The `Idempotency-Key` header (with a unique constraint in the DB) guarantees
that concurrent duplicate requests return the same payment instead of
creating two. The consumer also skips payments that are no longer `pending`
(at-least-once redelivery safety).

### Dead Letter Queue (DLQ)
Messages that failed after 3 attempts end up in the durable `outbox.dlq`
queue (RabbitMQ), where they are stored until handled manually via the
management UI at http://localhost:15672.

## Migrations

Alembic is wired in: the API container runs `alembic upgrade head` before
starting uvicorn. To create a new migration after changing models:

```bash
alembic revision --autogenerate -m "description"
```

## Hot reload (development)

The compose file bind-mounts `./src` into both containers and runs uvicorn /
faststream with `--reload`, so source edits apply on save. Dependency
changes (`pyproject.toml`) still require a rebuild: `docker compose build`.
