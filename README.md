# Payment Processing Service

Async payment processing microservice built with FastAPI, RabbitMQ (FastStream), and PostgreSQL.

## Setup

1. Copy the environment file (all connection strings and secrets live here, nothing is hardcoded):
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

## Statuses

`payments.status` is stored in PostgreSQL as `smallint` (0/1/2) and mapped to a
readable `PaymentStatus` IntEnum in code:

| smallint | Python            | API / webhook |
|----------|-------------------|---------------|
| 0        | PaymentStatus.PENDING   | `"pending"`   |
| 1        | PaymentStatus.SUCCEEDED | `"succeeded"` |
| 2        | PaymentStatus.FAILED    | `"failed"`    |

The API and webhook payloads keep the string contract; only the DB layer uses integers.

## Architecture

```
1. API (one transaction):
   INSERT payment (PENDING) + INSERT outbox (payment.new)

2. Outbox relay (polls the outbox table every 2s, FOR UPDATE SKIP LOCKED):
   sees payment.new -> publishes to RabbitMQ queue "payments.new" -> marks processed

3. Consumer (subscribed to payments.new):
   emulates gateway (2-5s, 90% success) -> ONE transaction:
   UPDATE payment status + INSERT outbox (payment.processed with webhook_url)

4. Outbox relay:
   sees payment.processed -> POST to webhook_url with up to 3 attempts (1s, 2s, 4s)
   success (2xx/3xx)            -> marked processed
   permanent failure (4xx)      -> message to "outbox.dlq", record closed with last_error
   transient failure (5xx/net)  -> retried; after 3 failed passes -> "outbox.dlq"
   infra error (broker/db down) -> record stays unprocessed, retried on the next pass
```

### Outbox Pattern
The API never publishes to RabbitMQ directly. Events are written to the
`outbox` table in the same transaction as business data, so a commit either
applies together with its event or not at all. The relay worker publishes
from the table, which guarantees at-least-once delivery.

### Idempotency
The `Idempotency-Key` header (with a unique constraint in the DB) guarantees
that concurrent duplicate requests return the same payment instead of
creating two. The consumer also skips payments that are no longer `PENDING`
(at-least-once redelivery safety).

### Dead Letter Queue (DLQ)
Messages that failed after 3 attempts end up in the durable `outbox.dlq`
queue (RabbitMQ), where they are stored until handled manually via the
management UI at http://localhost:15672.

## Migrations

Alembic is wired in: the API container runs `alembic upgrade head` before
starting uvicorn. The DB URL is taken from the `DATABASE_URL` environment
variable. To create a new migration after changing models:

```bash
alembic revision --autogenerate -m "description"
```

## Hot reload (development)

The compose file bind-mounts `./src` into both containers and runs uvicorn /
faststream with `--reload`, so source edits apply on save. Dependency
changes (`pyproject.toml`) still require a rebuild: `docker compose build`.
