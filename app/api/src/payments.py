from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import uuid4
from messaging.rabbitmq import publish_payment_event
from .schemas.payment import PaymentCreate, PaymentResponse
from models.models import Payment, PaymentStatus
from database import get_db
import json

router = APIRouter()

@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    payment_data: PaymentCreate,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db)
):
    # Check for existing payment with same idempotency key
    existing_payment = await db.execute(
        select(Payment).where(Payment.idempotency_key == idempotency_key)
    )
    existing_payment = existing_payment.scalar_one_or_none()

    if existing_payment:
        return PaymentResponse.from_orm(existing_payment)

    # Create new payment
    payment_id = str(uuid4())
    new_payment = Payment(
        id=payment_id,
        amount=payment_data.amount,
        currency=payment_data.currency.value,
        description=payment_data.description,
        metadata=payment_data.metadata,
        idempotency_key=idempotency_key,
        webhook_url=payment_data.webhook_url,
        status=PaymentStatus.PENDING
    )

    db.add(new_payment)
    await db.commit()
    await db.refresh(new_payment)

    # Publish event to RabbitMQ queue
    await publish_payment_event(payment_id)

    return PaymentResponse.from_orm(new_payment)

@router.get("/payments/{payment_id}", response_model=PaymentResponse)
async def get_payment(payment_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Payment).where(Payment.id == payment_id))
    payment = result.scalar_one_or_none()

    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )

    return PaymentResponse.from_orm(payment)