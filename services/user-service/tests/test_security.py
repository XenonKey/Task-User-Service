import uuid

import jwt

from app.config import settings
from app.security import create_access_token


def test_create_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "performer")

    payload = jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "performer"
    assert payload["type"] == "access"


def test_token_rejected_with_wrong_secret() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "performer")

    try:
        jwt.decode(token, "wrong-secret", algorithms=["HS256"])
        assert False, "expected InvalidSignatureError"
    except jwt.InvalidSignatureError:
        pass
