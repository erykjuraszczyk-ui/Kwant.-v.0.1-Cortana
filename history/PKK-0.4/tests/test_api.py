from fastapi.testclient import TestClient
from app.main import app, memory

client = TestClient(app)

def setup_function():
    memory.reset()

def payload(track_id="obj-1", observed_at="2026-10-22T12:00:00Z"):
    return {
        "source": "test-camera",
        "observed_at": observed_at,
        "observations": [{
            "track_id": track_id, "label": "person", "confidence": 0.95,
            "bbox": [0.1, 0.1, 0.7, 0.9]
        }]
    }

def test_health_and_version():
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/version").json()["version"] == "0.4.0"

def test_first_observation_creates_world_object():
    r = client.post("/perception/observations", json=payload())
    assert r.status_code == 200
    assert r.json()["accepted"] == 1
    state = client.get("/world/state").json()
    assert state["count"] == 1
    assert state["objects"][0]["label"] == "person"

def test_second_observation_updates_same_track():
    client.post("/perception/observations", json=payload())
    client.post("/perception/observations", json=payload(observed_at="2026-10-22T12:00:01Z"))
    obj = client.get("/world/state").json()["objects"][0]
    assert obj["observations_count"] == 2

def test_invalid_bbox_rejected():
    bad = payload()
    bad["observations"][0]["bbox"] = [0.8, 0.1, 0.2, 0.9]
    assert client.post("/perception/observations", json=bad).status_code == 422

def test_timezone_required():
    bad = payload(observed_at="2026-10-22T12:00:00")
    assert client.post("/perception/observations", json=bad).status_code == 422

def test_memory_reset():
    client.post("/perception/observations", json=payload())
    assert client.post("/memory/reset").json()["status"] == "reset"
    assert client.get("/world/state").json()["count"] == 0

def test_event_log_contains_first_seen():
    client.post("/perception/observations", json=payload())
    kinds = [e["event_type"] for e in client.get("/memory/events").json()["events"]]
    assert "object_first_seen" in kinds

def test_empty_observation_batch():
    p = payload()
    p["observations"] = []
    assert client.post("/perception/observations", json=p).json()["accepted"] == 0
