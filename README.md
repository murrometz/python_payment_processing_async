Файл: README.md
Относительный путь: ./README.md

markdown
Копировать
# Payment Processing Service

Async payment processing microservice built with FastAPI, RabbitMQ, and PostgreSQL.

## Setup

1. Copy environment file:
```bash
cp .env.example .env

Update .env with your actual values

Install dependencies:

```bash
poetry install
```

## Running with Docker
```bash
docker-compose up
```

Services will be available at:

API: http://localhost:8000
RabbitMQ Management: http://localhost:15672
PostgreSQL: localhost:5432

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
    "webhook_url": "https://example.com/webhook"
  }'
```

Get Payment
```bash
curl -X GET http://localhost:8000/api/v1/payments/{payment_id} \
  -H "X-API-Key: your_static_api_key_here"
```

## Architecture

The project follows a Modular Monorepo architecture with strict domain separation. Each component is an independent Python package with its own pyproject.toml.

## High-Level Flow
1. Client sends a POST /payments request to the API. 
2. API validates the request, saves the payment with PENDING status to PostgreSQL, and publishes a payments.new event to RabbitMQ. 
3. Consumer listens to the queue, processes the payment (emulating a 2-5 second gateway call), and updates the status in the database. 
4. Consumer creates an entry in the outbox table to guarantee webhook delivery. 
5. Outbox Processor (background task) reads unprocessed outbox messages and sends HTTP requests to the client's webhook_url. 

## Module Breakdown

### Core (payment-core)
  * Location: ./core/ 
  * Role: The single source of truth for business logic. 
  * Contents: SQLAlchemy models (Payment, OutboxMessage), Enums (PaymentStatus, Currency), and Pydantic schemas for data validation. 
  * Dependency: None (foundation).

### Database (payment-database)
* Location: ./database/ 
* Role: Database connection management. 
* Contents: Async engine, session factory (get_db), and SQLAlchemy Base. 
* Dependency: core.

### API (payment-api)
* Location: ./api/ 
* Role: HTTP interface. 
* Contents: FastAPI application, API Key authentication middleware, and routers for creating and retrieving payments. 
* Dependency: core, database, messaging.

### Consumer (payment-consumer)
* Location: ./consumer/ 
* Role: Asynchronous background worker. 
* Contents: FastStream broker subscriber that processes payments and updates DB status. 
* Dependency: core, database, messaging.

### Messaging (payment-messaging)
* Location: ./messaging/ 
* Role: Communication layer. 
* Contents: RabbitMQ broker configuration and event publishers. 
* Dependency: None.

## Reliability Patterns
### Outbox Pattern
Instead of publishing to RabbitMQ directly from the API (which risks data loss if the DB commit fails after the message is sent), we write to the outbox table within the same DB transaction. A separate process then reliably ships these messages.
### Idempotency
The Idempotency-Key header ensures that retrying a failed HTTP request does not create duplicate payments in the database.

### Dead Letter Queue (DLQ)
If the Consumer fails to process a message after 3 attempts, it is moved to the outbox.dlq queue for manual inspection, preventing infinite retry loops that block the queue.