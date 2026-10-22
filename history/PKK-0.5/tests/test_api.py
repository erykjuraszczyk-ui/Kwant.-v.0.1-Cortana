from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import create_app


def batch(track_id="person-1", bbox=None, observed_at=None):
    return {
        "source": "test-camera",
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "observations": [{"track_id": track_id, "label": "person", "confidence": 0.94,
                          "bbox": bbox or [0.1, 0.1, 0.4, 0.8]}]
    }


def make_client(tmp_path):
    app = create_app(str(tmp_path / "test.sqlite3"))
    return TestClient(app)


def test_health_version_and_stats(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/health").json()["status"] == "ok"
    assert c.get("/version").json()["version"] == "0.5.0"
    assert c.get("/memory/stats").json()["schema_version"] == 1


def test_persists_object_and_timeline(tmp_path):
    c = make_client(tmp_path)
    assert c.post("/perception/observations", json=batch()).status_code == 200
    state = c.get("/world/state").json()
    assert state["count"] == 1
    assert state["objects"][0]["track_id"] == "person-1"
    timeline = c.get("/memory/timeline?track_id=person-1").json()
    assert timeline["count"] == 1
    # A new application instance opens the same file and sees persisted data.
    c2 = make_client(tmp_path)
    assert c2.get("/world/state").json()["count"] == 1


def test_movement_event_detected(tmp_path):
    c = make_client(tmp_path)
    c.post("/perception/observations", json=batch())
    c.post("/perception/observations", json=batch(bbox=[0.25, 0.1, 0.55, 0.8]))
    kinds = [e["event_type"] for e in c.get("/memory/events").json()["events"]]
    assert "object_entered" in kinds
    assert "object_moved" in kinds


def test_detector_adapter_preserves_tracker_id(tmp_path):
    c = make_client(tmp_path)
    p = {"source": "yolo", "frame_id": "f001", "detections": [{"track_id": "track-9", "label": "car", "confidence": 0.88, "bbox": [0.1, 0.2, 0.6, 0.8]}]}
    r = c.post("/perception/detections", json=p)
    assert r.status_code == 200
    assert r.json()["objects"][0]["track_id"] == "track-9"


def test_adapter_without_track_id_uses_frame_scoped_id(tmp_path):
    c = make_client(tmp_path)
    p = {"source": "yolo", "frame_id": "f012", "detections": [{"label": "dog", "confidence": 0.75, "bbox": [0.1, 0.2, 0.6, 0.8]}]}
    r = c.post("/perception/detections", json=p)
    assert r.status_code == 200
    assert r.json()["objects"][0]["track_id"] == "yolo:f012:0"


def test_invalid_bbox_is_rejected(tmp_path):
    c = make_client(tmp_path)
    p = batch(bbox=[0.8, 0.1, 0.2, 0.8])
    assert c.post("/perception/observations", json=p).status_code == 422


def test_timezone_required(tmp_path):
    c = make_client(tmp_path)
    p = batch(observed_at="2026-10-22T12:00:00")
    assert c.post("/perception/observations", json=p).status_code == 422


def test_reset_clears_records_but_logs_reset_event(tmp_path):
    c = make_client(tmp_path)
    c.post("/perception/observations", json=batch())
    assert c.post("/memory/reset").json()["status"] == "reset"
    assert c.get("/world/state").json()["count"] == 0
    events = c.get("/memory/events").json()["events"]
    assert [e["event_type"] for e in events] == ["memory_reset"]
