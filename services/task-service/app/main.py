import logging

from fastapi import FastAPI

from .routers import tasks

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Task Service", version="1.0.0")

app.include_router(tasks.router)


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok"}
