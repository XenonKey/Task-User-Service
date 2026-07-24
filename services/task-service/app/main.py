import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .auth import load_public_key
from .routers import tasks

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await load_public_key()
    yield


app = FastAPI(title="Task Service", version="1.0.0", lifespan=lifespan)

app.include_router(tasks.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
