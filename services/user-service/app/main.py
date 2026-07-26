import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .kafka_consumer import consume_task_events
from .routers import auth, users

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(consume_task_events())
    try:
        yield
    finally:
        consumer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await consumer_task


app = FastAPI(title="User Service", version="1.0.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(users.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
