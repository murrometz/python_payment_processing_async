from sqlalchemy import Column, String, DateTime, Numeric, JSON, Enum, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()

class PaymentStatus(enum.Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"

class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True)
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    description = Column(String, nullable=True)
    metadata = Column(JSON, nullable=True)
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    idempotency_key = Column(String, unique=True, nullable=False)
    webhook_url = Column(String, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    processed_at = Column(DateTime, nullable=True)

class OutboxMessage(Base):
    __tablename__ = "outbox"
    
    id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    processed = Column(Boolean, default=False)