import uuid

import jwt

from app.security import PUBLIC_KEY, create_access_token, get_jwks


def test_create_access_token_roundtrip() -> None:
    user_id = uuid.uuid4()
    token = create_access_token(user_id, "performer")

    payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])

    assert payload["sub"] == str(user_id)
    assert payload["role"] == "performer"
    assert payload["type"] == "access"


def test_jwks_contains_public_key() -> None:
    jwks = get_jwks()
    assert len(jwks["keys"]) == 1
    assert jwks["keys"][0]["kty"] == "RSA"
