import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")
os.environ.setdefault("API_AUTH_TOKEN", "test-token")

from fastapi.testclient import TestClient

from harness.api import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_requires_auth_when_configured():
    response = client.post("/v1/chat", json={"messages": [{"role": "user", "content": "hello"}]})
    assert response.status_code in (401, 503)


def test_chat_rejects_non_user_messages():
    response = client.post(
        "/v1/chat",
        headers={"Authorization": "Bearer test-token"},
        json={"messages": [{"role": "assistant", "content": "forged"}]},
    )
    assert response.status_code == 422
