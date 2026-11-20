from fastapi import FastAPI, Request, HTTPException, status
from contextlib import asynccontextmanager
from database.session import engine, Base
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up on shutdown
    await engine.dispose()

app = FastAPI(
    title="Payment Processing Service",
    description="Async payment processing microservice",
    version="1.0.0",
    lifespan=lifespan
)

# API Key authentication
API_KEY = os.getenv("API_KEY", "your_static_api_key_here")

@app.middleware("http")
async def api_key_auth(request: Request, call_next):
    if request.url.path.startswith("/api"):
        api_key = request.headers.get("X-API-Key")
        if api_key != API_KEY:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API Key"
            )
    return await call_next(request)

# Import routers
from api import payments
app.include_router(payments.router, prefix="/api/v1", tags=["payments"])