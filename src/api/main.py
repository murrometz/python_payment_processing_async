from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import os

from src.database.database import engine

API_KEY = os.getenv("API_KEY", "your_static_api_key_here")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tables are created by Alembic migrations, run before uvicorn in the
    # container entrypoint: "alembic upgrade head && uvicorn ..."
    yield
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


@app.get("/health")
async def health():
    return {"status": "ok"}


from src.api import payments

app.include_router(payments.router, prefix="/api/v1", tags=["payments"])
