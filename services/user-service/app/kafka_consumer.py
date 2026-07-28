import json
import logging
import uuid

from aiokafka import AIOKafkaConsumer
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config import settings
from app.db import async_session_maker
from app.models import ProcessedEvent, User

logger = logging.getLogger(__name__)


async def _handle_task_completed(event: dict) -> None:
    event_id = uuid.UUID(event["event_id"])
    payload = event["payload"]
    performer_id = uuid.UUID(payload["performer_id"])
    reward = payload["reward"]

    async with async_session_maker() as session:
        async with session.begin():
            insert_stmt = pg_insert(ProcessedEvent).values(event_id=event_id).on_conflict_do_nothing()
            result = await session.execute(insert_stmt)
            if result.rowcount == 0:
                logger.info("Event %s already processed, skipping", event_id)
                return
            await session.execute(
                update(User).where(User.id == performer_id).values(balance=User.balance + reward)
            )
    logger.info("Applied reward %s to user %s for event %s", reward, performer_id, event_id)


async def consume_task_events() -> None:
    consumer = AIOKafkaConsumer(
        settings.kafka_topic,
        bootstrap_servers=settings.kafka_bootstrap_servers,
        group_id=settings.kafka_consumer_group,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        enable_auto_commit=True,
        auto_offset_reset="earliest",
    )
    await consumer.start()
    logger.info("Kafka consumer started, listening on topic '%s'", settings.kafka_topic)
    try:
        async for message in consumer:
            event = message.value
            if event.get("event_type") != "task.completed":
                continue
            try:
                await _handle_task_completed(event)
            except Exception:
                logger.exception("Failed to process event: %s", event)
    finally:
        await consumer.stop()
