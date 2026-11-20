from enum import IntEnum

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Numeric,
    JSON,
    Boolean,
    SmallInteger,
    func,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class PaymentStatus(IntEnum):
    """Payment status. Stored in the DB as smallint:
    0 -> PENDING, 1 -> SUCCEEDED, 2 -> FAILED."""

    PENDING = 0
    SUCCEEDED = 1
    FAILED = 2

    @property
    def as_string(self) -> str:
        """String representation for API and webhook payloads ("pending", ...)."""
        return self.name.lower()

    @classmethod
    def from_string(cls, value: str) -> "PaymentStatus":
        return cls[value.upper()]


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    description = Column(String, nullable=True)
    additional = Column(JSON, nullable=True)
    status = Column(
        SmallInteger,
        nullable=False,
        default=PaymentStatus.PENDING.value,
    )
    idempotency_key = Column(String, unique=True, nullable=False)
    webhook_url = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)


class OutboxMessage(Base):
    __tablename__ = "outbox"

    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processed = Column(Boolean, default=False, nullable=False)
    # Failed delivery passes (infra errors); after the limit the record goes to the DLQ
    attempts = Column(SmallInteger, nullable=False, default=0)
    last_error = Column(String, nullable=True)


Index("ix_outbox_processed_created", OutboxMessage.processed, OutboxMessage.created_at)
