from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

from src.database.database import engine
from src.core.models.models import Base
from src.messaging.rabbitmq import broker

API_KEY = os.getenv("API_KEY", "your_static_api_key_here")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fallback until Alembic migrations are wired in
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Connect the broker so the API can publish events
    await broker.start()
    yield
    await broker.close()
    await engine.dispose()

app = FastAPI(
    title="Payment Processing Service",
    description="Async payment processing microservice",
    version="1.0.0",
    lifespan=lifespan,
)

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    if request.url.path.startswith("/api"):
        api_key = request.headers.get("X-API-Key")
        if api_key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API Key"},
            )
    return await call_next(request)

from src.api import payments
app.include_router(payments.router, prefix="/api/v1", tags=["payments"])
