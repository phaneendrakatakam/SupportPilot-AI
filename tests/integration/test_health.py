from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_route_exists() -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_has_v2_fields() -> None:
    body = client.get("/health").json()
    assert body["database"] in {"up", "down"}
    assert "model" in body
    assert "embedding_model" in body
