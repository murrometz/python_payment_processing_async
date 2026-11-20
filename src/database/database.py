from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.config import settings
from src.core.models.models import Base

engine = create_async_engine(settings.database_url, echo=settings.db_echo)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# Dependency for FastAPI to get the DB session
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
