from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any

from src.core.models.models import PaymentStatus


class Currency(str, Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class PaymentCreate(BaseModel):
    amount: float = Field(..., gt=0, description="Payment amount must be greater than 0")
    currency: Currency
    description: Optional[str] = None
    additional: Optional[Dict[str, Any]] = None
    webhook_url: str = Field(..., description="URL for webhook notifications")


class PaymentResponse(BaseModel):
    id: str
    amount: float
    currency: Currency
    description: Optional[str] = None
    additional: Optional[Dict[str, Any]] = None
    status: str
    idempotency_key: str
    webhook_url: str
    created_at: datetime
    processed_at: Optional[datetime] = None

    @field_validator("status", mode="before")
    @classmethod
    def status_to_api_string(cls, value):
        if isinstance(value, PaymentStatus):
            return value.as_string
        if isinstance(value, int):
            return PaymentStatus(value).as_string
        return value

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
