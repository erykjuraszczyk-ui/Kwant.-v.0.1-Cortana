from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path
import re
from .models import ObservationBatch, DetectorBatch, ObjectObservation
from .store import SQLiteMemory
from .inference import predict_track, summarize_recent_activity
from .fusion import ContextEvent, ContextMemory, analyze_fusion
from .decision import DecisionRequest, make_decision
from .cortana import ChatRequest, CortanaChat


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="PKK — Percepcyjny Komputer Kwantowy",
        version="1.0.0",
        description="PKK 1.0: zintegrowany prototyp percepcji, trwałej pamięci, fuzji, wnioskowania, rekomendacji i dialogu Cortany z opcjonalnym głosem w przeglądarce."
    )
    store = SQLiteMemory(db_path)
    context_memory = ContextMemory(store.path)
    app.state.store = store
    app.state.context_memory = context_memory
    cortana = CortanaChat(store.path, store, context_memory)
    app.state.cortana = cortana

    @app.get("/health")
    def health():
        return {"status": "ok", "version": app.version, "storage": "sqlite", "inference": "enabled", "chat": "enabled", "voice": "browser-optional"}

    @app.get("/version")
    def version():
        return {"name": "PKK", "version": app.version, "stage": "integrated-perception-and-dialog-prototype"}

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

    @app.post("/decision/evaluate")
    def evaluate_decision(request: DecisionRequest):
        return make_decision(
            store, context_memory, request.goal,
            request.horizon_seconds, request.include_context
        )

    @app.get("/decision/policy")
    def decision_policy():
        return {
            "external_actions_enabled": False,
            "destructive_actions_enabled": False,
            "automatic_camera_or_microphone_activation": False,
            "human_approval_required_for_future_external_actions": True,
            "principles": [
                "Oddzielaj obserwacje od interpretacji.",
                "Zwracaj jawne źródła dowodów i niepewność.",
                "Nie wykonuj działań zewnętrznych w PKK 0.8.",
                "Brak danych nie jest dowodem braku zdarzenia."
            ]
        }

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


    @app.get("/cortana", include_in_schema=False)
    def cortana_ui():
        return FileResponse(Path(__file__).parent / "static" / "cortana.html", media_type="text/html")

    @app.get("/cortana/status")
    def cortana_status():
        return cortana.status()

    @app.get("/system/status")
    def system_status():
        stats = store.stats()
        fusion = analyze_fusion(store, context_memory, window_seconds=30)
        decision = make_decision(
            store, context_memory, "system_status",
            horizon_seconds=30, include_context=True
        )
        chat_status = cortana.status()
        return {
            "name": "PKK",
            "version": app.version,
            "stage": "integrated-perception-and-dialog-prototype",
            "components": {
                "perception_api": "ready",
                "persistent_memory": "ready",
                "world_model": "ready",
                "motion_inference": "ready",
                "context_fusion": "ready",
                "decision_engine": "ready",
                "cortana_dialog": "ready",
                "browser_voice": "optional_client_capability"
            },
            "storage": stats,
            "context": {
                "modalities_present": fusion.get("modalities_present", []),
                "evidence_level": fusion.get("evidence_level"),
                "summary": fusion.get("summary")
            },
            "recommendation": {
                "action": decision.get("action"),
                "rationale": decision.get("rationale")
            },
            "chat": {
                "provider": chat_status.get("configured_provider"),
                "local_only": chat_status.get("local_only"),
                "api_key_configured": chat_status.get("api_key_configured")
            },
            "limitations": [
                "Obecna percepcja przyjmuje wyniki detektora; ten pakiet nie uruchamia automatycznie kamery do detekcji obiektów.",
                "Głos jest opcjonalnym interfejsem przeglądarkowym i zależy od obsługi Web Speech API.",
                "Rozpoznawanie mowy w przeglądarce może być realizowane przez usługę dostawcy przeglądarki; nie należy zakładać, że działa całkowicie lokalnie.",
                "PKK 1.0 jest klasycznym prototypem AI i nie używa fizycznego komputera kwantowego."
            ]
        }

    @app.post("/cortana/chat")
    def cortana_chat(request: ChatRequest):
        return cortana.chat(request)

    @app.get("/cortana/conversations")
    def cortana_conversations(limit: int = Query(default=30, ge=1, le=100)):
        return {"conversations": cortana.list_conversations(limit=limit)}

    @app.get("/cortana/conversations/{conversation_id}")
    def cortana_history(conversation_id: str, limit: int = Query(default=30, ge=1, le=100)):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", conversation_id):
            raise HTTPException(status_code=422, detail="Invalid conversation_id")
        return {"conversation_id": conversation_id, "messages": cortana.history(conversation_id, limit=limit)}

    @app.delete("/cortana/conversations/{conversation_id}")
    def cortana_delete_conversation(conversation_id: str):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", conversation_id):
            raise HTTPException(status_code=422, detail="Invalid conversation_id")
        return cortana.delete_conversation(conversation_id)

    return app


app = create_app()
