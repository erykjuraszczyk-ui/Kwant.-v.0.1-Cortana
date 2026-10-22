from fastapi import FastAPI, HTTPException, Query
from .models import ObservationBatch, DetectorBatch, ObjectObservation
from .store import SQLiteMemory
from .inference import predict_track, summarize_recent_activity
from .fusion import ContextEvent, ContextMemory, analyze_fusion


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="PKK — Percepcyjny Komputer Kwantowy",
        version="0.7.0",
        description="PKK 0.7: fuzja danych z percepcji wzrokowej i zdarzeń kontekstowych, trwała pamięć SQLite i objaśnialne reguły. Klasyczny prototyp AI."
    )
    store = SQLiteMemory(db_path)
    context_memory = ContextMemory(store.path)
    app.state.store = store
    app.state.context_memory = context_memory

    @app.get("/health")
    def health():
        return {"status": "ok", "version": app.version, "storage": "sqlite", "inference": "enabled"}

    @app.get("/version")
    def version():
        return {"name": "PKK", "version": app.version, "stage": "multimodal-context-fusion"}

    @app.post("/perception/observations")
    def ingest_observations(batch: ObservationBatch):
        return store.ingest(batch)

    @app.post("/perception/detections")
    def ingest_detections(batch: DetectorBatch):
        converted = []
        for index, detection in enumerate(batch.detections):
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
        base_result = store.reset()
        context_result = context_memory.reset()
        return {"status": "reset", "database": "sqlite", "context_events_removed": context_result["deleted"]}

    @app.post("/context/events")
    def ingest_context_event(event: ContextEvent):
        return context_memory.record(event)

    @app.get("/context/events")
    def list_context_events(limit: int = Query(default=100, ge=1, le=500),
                            modality: str | None = Query(default=None, pattern="^(audio|text|vision|environment)$")):
        events = context_memory.list_events(limit=limit, modality=modality)
        return {"events": events, "count": len(events)}

    @app.post("/context/reset")
    def reset_context():
        return context_memory.reset()

    @app.get("/fusion/state")
    def fusion_state(window_seconds: int = Query(default=10, ge=1, le=300)):
        return analyze_fusion(store, context_memory, window_seconds=window_seconds)

    @app.get("/fusion/timeline")
    def fusion_timeline(limit: int = Query(default=100, ge=1, le=500)):
        return context_memory.fused_timeline(store, limit=limit)

    @app.get("/inference/predict/{track_id}")
    def inference_predict(track_id: str, horizon_seconds: float = Query(default=1.0, ge=0.1, le=10.0),
                         limit: int = Query(default=30, ge=2, le=100)):
        result = predict_track(store, track_id, horizon_seconds=horizon_seconds, limit=limit)
        if result["status"] == "unavailable":
            raise HTTPException(status_code=404, detail=result)
        return result

    @app.get("/inference/summary")
    def inference_summary(window_seconds: int = Query(default=30, ge=1, le=3600)):
        return summarize_recent_activity(store, window_seconds=window_seconds)

    return app


app = create_app()
