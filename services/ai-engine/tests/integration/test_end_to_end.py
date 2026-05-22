import pytest
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

# More E2E pipeline tests would use fixtures to simulate RTSP feeds
# and verify that Redis streams receive the correct metadata.
