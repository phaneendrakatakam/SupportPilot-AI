from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_route_exists() -> None:
    response = client.get("/health")

    assert response.status_code == 200

    body = response.json()

    assert body["status"] in {
        "ok",
        "degraded",
    }

    assert body["database"] in {
        "up",
        "down",
    }

    assert body["agent"] in {
        "configured",
        "not-configured",
    }

    assert isinstance(
        body["model"],
        str,
    )

    assert body["model"]