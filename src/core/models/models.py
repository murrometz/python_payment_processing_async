import enum
import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import false, func, text

Base = declarative_base()


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


def _enum_values(cls):
    return [e.value for e in cls]


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    description = Column(String(255), nullable=True)
    # NB: `metadata` is a reserved attribute name in SQLAlchemy Declarative,
    # so the Python attribute is `payment_metadata`; the DB column is `metadata`.
    payment_metadata = Column("metadata", JSON, nullable=True)
    status = Column(
        SAEnum(PaymentStatus, name="payment_status", native_enum=False, length=16,
               values_callable=_enum_values),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=text("'pending'"),
    )
    idempotency_key = Column(String(255), nullable=False, unique=True)
    webhook_url = Column(String(2048), nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    processed_at = Column(DateTime, nullable=True)


class OutboxMessage(Base):
    __tablename__ = "outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_type = Column(String(64), nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    processed = Column(Boolean, nullable=False, default=False, server_default=false())
    processed_at = Column(DateTime, nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default=text("0"))
    last_error = Column(Text, nullable=True)

    __table_args__ = (
        Index("ix_outbox_processed_created", "processed", "created_at"),
    )
