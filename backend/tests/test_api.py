"""
Integration tests for FastAPI REST API endpoints.
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_ready_endpoint():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert "model_loaded" in data
    assert "pose_loaded" in data

def test_login_demo_code():
    # Valid code
    response = client.post("/api/login", json={"access_code": "demo2026"})
    assert response.status_code == 200
    assert "token" in response.json()

    # Invalid code
    res_fail = client.post("/api/login", json={"access_code": "wrong_pass"})
    assert res_fail.status_code == 401

def test_session_lifecycle():
    # Create session
    res = client.post("/api/sessions", json={"camera_label": "Test Cam"})
    assert res.status_code == 200
    session_id = res.json()["session_id"]
    assert "ws_ticket" in res.json()

    # Get events
    res_events = client.get(f"/api/sessions/{session_id}/events")
    assert res_events.status_code == 200
    assert isinstance(res_events.json(), list)

    # Stop session
    res_stop = client.post(f"/api/sessions/{session_id}/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] == "stopped"
