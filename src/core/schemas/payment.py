from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"

class PaymentStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Payment amount must be greater than 0")
    currency: Currency
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    webhook_url: str = Field(..., description="URL for webhook notifications")

class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: Currency
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    status: PaymentStatus
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
