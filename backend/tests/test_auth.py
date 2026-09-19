from datetime import UTC, datetime, timedelta

import jwt

from backend.app.core.config import get_settings
from backend.app.core.security import User, create_access_token

settings = get_settings()


def test_login_returns_a_bearer_token(anon_client):
    response = anon_client.post(
        "/api/v1/auth/token", data={"username": "analyst", "password": "analyst123"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    payload = jwt.decode(
        body["access_token"], settings.jwt_secret, algorithms=[settings.jwt_algorithm]
    )
    assert payload["sub"] == "analyst"
    assert payload["role"] == "analyst"


def test_login_with_wrong_password_is_rejected(anon_client):
    response = anon_client.post(
        "/api/v1/auth/token", data={"username": "analyst", "password": "wrong"}
    )
    assert response.status_code == 401


def test_endpoints_require_a_token(anon_client):
    assert anon_client.get("/api/v1/flags").status_code == 401


def test_a_valid_token_grants_access(anon_client):
    token = create_access_token(User(username="analyst", role="analyst"))
    response = anon_client.get("/api/v1/flags", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_a_tampered_token_is_rejected(anon_client):
    forged = jwt.encode(
        {"sub": "analyst", "role": "analyst", "exp": datetime.now(UTC) + timedelta(hours=1)},
        "not-the-real-secret-but-long-enough-to-satisfy-rfc7518",
        algorithm=settings.jwt_algorithm,
    )
    response = anon_client.get("/api/v1/flags", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_an_expired_token_is_rejected(anon_client):
    expired = jwt.encode(
        {
            "sub": "analyst",
            "role": "analyst",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    response = anon_client.get("/api/v1/flags", headers={"Authorization": f"Bearer {expired}"})
    assert response.status_code == 401
    assert "expired" in response.json()["detail"].lower()


def test_viewer_can_read(viewer_client, seeded):
    assert viewer_client.get("/api/v1/flags").status_code == 200


def test_viewer_cannot_freeze_an_account(viewer_client, seeded):
    response = viewer_client.patch(
        f"/api/v1/accounts/{seeded['account'].id}/status",
        json={"status": "frozen", "reason": "Trying without permission"},
    )
    assert response.status_code == 403


def test_viewer_cannot_review_a_flag(viewer_client, seeded):
    response = viewer_client.patch(
        f"/api/v1/flags/{seeded['flag'].id}/status", json={"status": "confirmed"}
    )
    assert response.status_code == 403
