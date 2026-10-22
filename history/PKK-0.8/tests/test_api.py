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
    assert c.get("/version").json()["version"] == "0.8.0"
    assert c.get("/memory/stats").json()["schema_version"] == 2


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


def test_prediction_reports_insufficient_data_for_single_observation(tmp_path):
    c = make_client(tmp_path)
    c.post("/perception/observations", json=batch())
    result = c.get("/inference/predict/person-1").json()
    assert result["status"] == "insufficient_data"
    assert result["reason"] == "need_two_distinct_timestamps"


def test_prediction_estimates_rightward_motion(tmp_path):
    from datetime import timedelta
    c = make_client(tmp_path)
    t0 = datetime.now(timezone.utc)
    c.post("/perception/observations", json=batch(
        bbox=[0.10, 0.10, 0.30, 0.70], observed_at=t0.isoformat()))
    c.post("/perception/observations", json=batch(
        bbox=[0.15, 0.10, 0.35, 0.70], observed_at=(t0 + timedelta(seconds=1)).isoformat()))
    c.post("/perception/observations", json=batch(
        bbox=[0.20, 0.10, 0.40, 0.70], observed_at=(t0 + timedelta(seconds=2)).isoformat()))
    result = c.get("/inference/predict/person-1?horizon_seconds=1").json()
    assert result["status"] == "estimated"
    assert result["velocity_normalized_per_second"][0] > 0
    assert result["predicted_center"][0] > result["current_center"][0]
    assert result["method"] == "linear_regression_of_bbox_centers"


def test_inference_summary_matches_movement_rule(tmp_path):
    from datetime import timedelta
    c = make_client(tmp_path)
    t0 = datetime.now(timezone.utc)
    c.post("/perception/observations", json=batch(
        bbox=[0.10, 0.10, 0.30, 0.70], observed_at=t0.isoformat()))
    c.post("/perception/observations", json=batch(
        bbox=[0.20, 0.10, 0.40, 0.70], observed_at=(t0 + timedelta(seconds=1)).isoformat()))
    result = c.get("/inference/summary?window_seconds=3600").json()
    movement = next(rule for rule in result["rules"] if rule["rule"] == "movement_observed")
    assert movement["matched"] is True
    assert movement["event_count"] >= 1


def test_prediction_returns_404_for_unknown_track(tmp_path):
    c = make_client(tmp_path)
    assert c.get("/inference/predict/missing-track").status_code == 404


def test_context_event_is_persisted_and_filtered(tmp_path):
    c = make_client(tmp_path)
    from datetime import datetime, timezone
    event = {
        "modality": "audio", "event_type": "speech_detected", "source": "local-test",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.8, "summary": "Mowa wykryta, bez transkrypcji.", "entities": []
    }
    r = c.post("/context/events", json=event)
    assert r.status_code == 200
    assert r.json()["stored"] is True
    got = c.get("/context/events?modality=audio").json()
    assert got["count"] == 1
    assert got["events"][0]["event_type"] == "speech_detected"


def test_fusion_reports_temporal_overlap_not_identity_claim(tmp_path):
    from datetime import datetime, timezone
    c = make_client(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    visual = {
        "source": "camera-test", "observed_at": now,
        "observations": [{
            "track_id": "person-1", "label": "person", "confidence": 0.94,
            "bbox": [0.1, 0.1, 0.3, 0.7]
        }]
    }
    context = {
        "modality": "audio", "event_type": "speech_detected", "source": "local-mic-module",
        "observed_at": now, "confidence": 0.8,
        "summary": "Mowa wykryta; transkrypcja wyłączona.", "entities": []
    }
    assert c.post("/perception/observations", json=visual).status_code == 200
    assert c.post("/context/events", json=context).status_code == 200
    fused = c.get("/fusion/state?window_seconds=20").json()
    assert fused["evidence_level"] == "multiple_modalities_temporally_aligned"
    assert len(fused["temporal_correlations"]) == 1
    assert "nie oznacza" in fused["temporal_correlations"][0]["interpretation"]


def test_timezone_required_for_context_event(tmp_path):
    c = make_client(tmp_path)
    event = {
        "modality": "audio", "event_type": "sound", "source": "test",
        "observed_at": "2026-10-22T12:00:00", "confidence": 0.5,
        "summary": "test"
    }
    assert c.post("/context/events", json=event).status_code == 422


def test_fusion_timeline_contains_vision_and_audio(tmp_path):
    from datetime import datetime, timezone
    c = make_client(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    c.post("/perception/observations", json={
        "source": "camera-test", "observed_at": now,
        "observations": [{"track_id": "obj-1", "label": "cup", "confidence": .9, "bbox": [0.1,0.1,0.3,0.3]}]
    })
    c.post("/context/events", json={
        "modality": "environment", "event_type": "light_change", "source": "sensor-1",
        "observed_at": now, "confidence": .7, "summary": "Zmiana oświetlenia"
    })
    timeline = c.get("/fusion/timeline").json()
    assert {x["modality"] for x in timeline["items"]} >= {"vision", "environment"}


def test_memory_reset_clears_context_too(tmp_path):
    c = make_client(tmp_path)
    c.post("/context/events", json={
        "modality": "text", "event_type": "note", "source": "test",
        "confidence": 1, "summary": "temporary"
    })
    r = c.post("/memory/reset")
    assert r.status_code == 200
    assert c.get("/context/events").json()["count"] == 0


def test_summary_limit_and_input_validation(tmp_path):
    c = make_client(tmp_path)
    oversized = {
        "modality": "audio", "event_type": "speech_detected", "source": "test",
        "confidence": 0.8, "summary": "x" * 501
    }
    assert c.post("/context/events", json=oversized).status_code == 422
    assert c.get("/fusion/state?window_seconds=0").status_code == 422


def test_decision_without_data_recommends_observe_more(tmp_path):
    c = make_client(tmp_path)
    result = c.post("/decision/evaluate", json={"goal": "test", "horizon_seconds": 10, "include_context": True})
    assert result.status_code == 200
    data = result.json()
    assert data["action"] == "observe_more"
    assert data["execution"] == "none"
    assert data["policy"]["external_actions_enabled"] is False
    assert data["uncertainty"]


def test_decision_reports_evidence_when_world_has_object(tmp_path):
    from datetime import datetime, timezone
    c = make_client(tmp_path)
    now = datetime.now(timezone.utc).isoformat()
    c.post("/perception/observations", json={
        "source": "camera-test", "observed_at": now,
        "observations": [{"track_id": "cup-1", "label": "cup", "confidence": .9, "bbox": [0.1,0.1,0.3,0.3]}]
    })
    result = c.post("/decision/evaluate", json={"goal": "scene summary", "horizon_seconds": 10, "include_context": True})
    assert result.status_code == 200
    data = result.json()
    assert data["action"] == "report"
    assert any("Aktywne obiekty" in line for line in data["evidence"])


def test_decision_policy_forbids_external_actions(tmp_path):
    c = make_client(tmp_path)
    policy = c.get("/decision/policy").json()
    assert policy["external_actions_enabled"] is False
    assert policy["destructive_actions_enabled"] is False
    assert policy["automatic_camera_or_microphone_activation"] is False


def test_decision_request_limits_horizon(tmp_path):
    c = make_client(tmp_path)
    assert c.post("/decision/evaluate", json={"goal": "test", "horizon_seconds": 9999}).status_code == 422
