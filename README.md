# Payment Processing Service

Async payment processing microservice built with FastAPI, RabbitMQ, and PostgreSQL.

## Setup

1. Copy environment file:
```bash
cp .env.example .env
```

2. Update `.env` with your actual values

3. Install dependencies:
```bash
poetry install
```

## Running with Docker

```bash
docker-compose up
```

Services will be available at:
- API: http://localhost:8000
- RabbitMQ Management: http://localhost:15672
- PostgreSQL: localhost:5432

## API Usage

### Create Payment

```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_static_api_key_here" \
  -H "Idempotency-Key: unique-key-123" \
  -d '{
    "amount": 100.50,
    "currency": "USD",
    "description": "Test payment",
    "webhook_url": "https://example.com/webhook"
  }'
```

### Get Payment

```bash
curl -X GET http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: your_static_api_key_here"
```

## Architecture

- **API Service**: Handles HTTP requests and publishes events
- **Consumer**: Processes payments and sends webhooks
- **Outbox Pattern**: Guarantees webhook delivery
- **Idempotency**: Prevents duplicate payments
- **DLQ**: Handles failed messages after retries