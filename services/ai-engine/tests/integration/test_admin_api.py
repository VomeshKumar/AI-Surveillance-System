import pytest
from app.api.main import app
from fastapi.testclient import TestClient

client = TestClient(app)

def test_assign_cameras():
    response = client.post("/api/cameras/assign-cameras", json=["rtsp://cam1", "rtsp://cam2"])
    assert response.status_code == 200
    assert response.json()["count"] == 2
