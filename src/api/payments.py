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
        additional=payment_data.additional,
        idempotency_key=idempotency_key,
        webhook_url=payment_data.webhook_url,
        status=PaymentStatus.PENDING.value,
    )

    # Outbox pattern: the "payment.new" event is written to the outbox table
    # in the SAME transaction as the payment itself. The outbox relay worker
    # publishes it to RabbitMQ afterwards - so the event can never be lost
    # after a successful commit.
    outbox_entry = OutboxMessage(
        id=str(uuid4()),
        event_type="payment.new",
        payload={"payment_id": payment_id},
        processed=False,
    )

    db.add(new_payment)
    db.add(outbox_entry)

    # Handle the idempotency race: two concurrent requests with the same
    # Idempotency-Key - the loser of the unique constraint returns the winner's payment
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(select(Payment).where(Payment.idempotency_key == idempotency_key))
        existing_payment = result.scalar_one_or_none()
        if existing_payment:
            return PaymentResponse.model_validate(existing_payment)
        raise HTTPException(status_code=500, detail="Failed to create payment")

    await db.refresh(new_payment)
    return PaymentResponse.model_validate(new_payment)


@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return PaymentResponse.model_validate(payment)
