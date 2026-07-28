import asyncio
import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from sqlalchemy import select, update

from app.config import settings
from app.db import async_session_maker
from app.models import Outbox

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def serialize_event(row: Outbox) -> bytes:
    event = {
        "event_id": str(row.id),
        "event_type": row.event_type,
        "aggregate_id": str(row.aggregate_id),
        "payload": row.payload,
        "created_at": row.created_at.isoformat(),
    }
    return json.dumps(event).encode("utf-8")


async def _publish_batch(producer: AIOKafkaProducer) -> int:
    async with async_session_maker() as session:
        result = await session.execute(
            select(Outbox)
            .where(Outbox.published_at.is_(None))
            .order_by(Outbox.created_at)
            .limit(settings.outbox_batch_size)
        )
        rows = result.scalars().all()

        published = 0
        for row in rows:
            try:
                await producer.send_and_wait(
                    settings.kafka_topic,
                    key=str(row.aggregate_id).encode("utf-8"),
                    value=serialize_event(row),
                )
                await session.execute(
                    update(Outbox).where(Outbox.id == row.id).values(published_at=datetime.now(timezone.utc))
                )
                await session.commit()
                published += 1
            except Exception:
                logger.exception("Failed to publish outbox event %s, will retry later", row.id)
                await session.rollback()
        return published


async def run() -> None:
    producer = AIOKafkaProducer(bootstrap_servers=settings.kafka_bootstrap_servers, acks="all")
    await producer.start()
    logger.info(
        "Outbox relay started, polling every %.1fs (topic=%s)",
        settings.outbox_poll_interval_seconds,
        settings.kafka_topic,
    )
    try:
        while True:
            try:
                published = await _publish_batch(producer)
                if published:
                    logger.info("Published %s event(s)", published)
            except Exception:
                logger.exception("Error while polling outbox")
            await asyncio.sleep(settings.outbox_poll_interval_seconds)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(run())
