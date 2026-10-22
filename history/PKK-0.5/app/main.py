import os
from datetime import datetime, timezone
from fastapi import FastAPI, Query
from .models import ObservationBatch, DetectorBatch, ObjectObservation
from .store import SQLiteMemory


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="PKK — Percepcyjny Komputer Kwantowy",
        version="0.5.0",
        description="PKK 0.5: trwała pamięć, oś czasu obserwacji i prosty model świata. Klasyczny prototyp AI."
    )
    store = SQLiteMemory(db_path)
    app.state.store = store

    @app.get("/health")
    def health():
        return {"status": "ok", "version": app.version, "storage": "sqlite"}

    @app.get("/version")
    def version():
        return {"name": "PKK", "version": app.version, "stage": "persistent-perception-memory"}

    @app.post("/perception/observations")
    def ingest_observations(batch: ObservationBatch):
        return store.ingest(batch)

    @app.post("/perception/detections")
    def ingest_detections(batch: DetectorBatch):
        converted = []
        for index, detection in enumerate(batch.detections):
            # Without a tracker ID, frame-scoped IDs intentionally do not imply identity across frames.
            track_id = detection.track_id or f"{batch.source}:{batch.frame_id}:{index}"
            converted.append(ObjectObservation(track_id=track_id, label=detection.label,
                                               confidence=detection.confidence, bbox=detection.bbox))
        observations = ObservationBatch(source=batch.source, observed_at=batch.observed_at, observations=converted)
        response = store.ingest(observations)
        response["adapter"] = "detector-output"
        response["identity_note"] = "A missing track_id is replaced with a frame-scoped ID; use a tracker for cross-frame identity."
        return response

    @app.get("/world/state")
    def world_state():
        objects = store.state()
        return {"objects": objects, "count": len(objects)}

    @app.get("/memory/events")
    def memory_events(limit: int = Query(default=100, ge=1, le=500), since_id: int | None = Query(default=None, ge=0)):
        events = store.events(limit=limit, since_id=since_id)
        return {"events": events, "count": len(events)}

    @app.get("/memory/timeline")
    def memory_timeline(track_id: str | None = None, limit: int = Query(default=100, ge=1, le=500)):
        items = store.timeline(track_id=track_id, limit=limit)
        return {"observations": items, "count": len(items)}

    @app.get("/memory/stats")
    def memory_stats():
        return store.stats()

    @app.post("/memory/reset")
    def reset_memory():
        return store.reset()

    return app


app = create_app()
