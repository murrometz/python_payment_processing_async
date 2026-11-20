from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os

# Importing Base from Core to ensure models are imported and registered
from core.models.models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/payments")

# Create the async engine instance
# echo=True logs all SQL queries to the console (useful for debugging)
engine = create_async_engine(DATABASE_URL, echo=True)

# Create a configured "Session" class
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

# Dependency for FastAPI to get the DB session
async def get_db():
    """
    Yields a database session to the path operation function.
    Ensures the session is closed after the request is finished.
    """
    async with AsyncSessionLocal() as session:
        yield session