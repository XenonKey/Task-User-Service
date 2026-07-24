import json
import uuid
from datetime import datetime, timezone

from app.main import serialize_event
from app.models import Outbox


def test_serialize_event_produces_expected_envelope() -> None:
    row = Outbox(
        id=uuid.uuid4(),
        aggregate_id=uuid.uuid4(),
        event_type="task.completed",
        payload={"task_id": "abc", "performer_id": "def", "reward": "10.00"},
        created_at=datetime.now(timezone.utc),
        published_at=None,
    )

    event = json.loads(serialize_event(row))

    assert event["event_id"] == str(row.id)
    assert event["event_type"] == "task.completed"
    assert event["aggregate_id"] == str(row.aggregate_id)
    assert event["payload"] == row.payload
