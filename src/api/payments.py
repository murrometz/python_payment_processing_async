from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models.models import OutboxMessage, Payment, PaymentStatus
from src.core.schemas.payment import PaymentCreate, PaymentResponse
from src.database.database import get_db

router = APIRouter()


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    payment_data: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    # Idempotency: return the existing payment on repeated requests
    result = await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
    existing_payment = result.scalar_one_or_none()
    if existing_payment:
        return PaymentResponse.model_validate(existing_payment)

    payment_id = str(uuid4())
    new_payment = Payment(
        id=payment_id,
        amount=payment_data.amount,
        currency=payment_data.currency.value,
        description=payment_data.description,
        # `metadata` is reserved by SQLAlchemy Declarative; the attribute is
        # payment_metadata while the DB column stays `metadata`
        payment_metadata=payment_data.metadata,
        idempotency_key=idempotency_key,
        webhook_url=payment_data.webhook_url,
        status=PaymentStatus.PENDING,
    )

    # Classic outbox: the event is written to the outbox table in the SAME
    # transaction as the business data. No direct publish to RabbitMQ here:
    # the outbox worker publishes it after the commit, so a crash between
    # commit and publish can never lose the event.
    outbox_entry = OutboxMessage(
        event_type="payment.new",
        payload={
            "event": "payment.new",
            "payment_id": payment_id,
            "attempt": 0,
        },
    )

    db.add(new_payment)
    db.add(outbox_entry)
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent request with the same Idempotency-Key: return the winner
        await db.rollback()
        result = await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
        winner = result.scalar_one_or_none()
        if winner:
            return PaymentResponse.model_validate(winner)
        raise

    await db.refresh(new_payment)
    return PaymentResponse.model_validate(new_payment)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentResponse.model_validate(payment)
