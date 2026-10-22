"""Context-event storage and transparent multimodal fusion for PKK 0.7.

The module accepts already-derived metadata; it does not capture or store raw audio/video.
Correlations are temporal co-occurrences, not claims about identity, causality, or meaning.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .store import SQLiteMemory, dt_to_str, parse_dt


class ContextEvent(BaseModel):
    modality: Literal["audio", "text", "vision", "environment"]
    event_type: str = Field(min_length=1, max_length=80)
    source: str = Field(min_length=1, max_length=96)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    summary: str = Field(default="", max_length=500)
    entities: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("observed_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value.astimezone(timezone.utc)

    @field_validator("entities")
    @classmethod
    def entities_limited(cls, values: list[str]) -> list[str]:
        return [v.strip()[:96] for v in values if v and v.strip()]


class ContextMemory:
    """Stores derived audio/text/environment events in the same SQLite file as PKK's world state."""
    def __init__(self, path: str | None = None):
        raw = path or os.getenv("PKK_DB_PATH", "data/pkk.sqlite3")
        self.path = raw
        if raw != ":memory:":
            Path(raw).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        if self.path == ":memory:":
            raise ValueError("Use a file-backed SQLite path for persistent context storage")
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS context_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                modality TEXT NOT NULL CHECK(modality IN ('audio','text','vision','environment')),
                event_type TEXT NOT NULL,
                source TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
                summary TEXT NOT NULL DEFAULT '',
                entities_json TEXT NOT NULL DEFAULT '[]'
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_events_time ON context_events(observed_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_context_events_modality_time ON context_events(modality, observed_at)")
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            conn.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES(?, ?)",
                (2, dt_to_str(datetime.now(timezone.utc)))
            )

    def record(self, event: ContextEvent) -> dict[str, Any]:
        with self.connect() as conn:
            cur = conn.execute(
                """INSERT INTO context_events(modality,event_type,source,observed_at,confidence,summary,entities_json)
                   VALUES(?,?,?,?,?,?,?)""",
                (event.modality, event.event_type, event.source, dt_to_str(event.observed_at),
                 event.confidence, event.summary, json.dumps(event.entities, ensure_ascii=False))
            )
            return {
                "id": cur.lastrowid,
                "modality": event.modality,
                "event_type": event.event_type,
                "source": event.source,
                "observed_at": dt_to_str(event.observed_at),
                "confidence": event.confidence,
                "summary": event.summary,
                "entities": event.entities,
                "stored": True,
            }

    def list_events(self, limit: int = 100, modality: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if modality:
                rows = conn.execute(
                    "SELECT * FROM context_events WHERE modality=? ORDER BY id DESC LIMIT ?",
                    (modality, limit)
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM context_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._row_dict(r) for r in reversed(rows)]

    def _row_dict(self, row) -> dict[str, Any]:
        return {
            "id": row["id"], "modality": row["modality"], "event_type": row["event_type"],
            "source": row["source"], "observed_at": row["observed_at"],
            "confidence": row["confidence"], "summary": row["summary"],
            "entities": json.loads(row["entities_json"])
        }

    def reset(self) -> dict[str, int]:
        with self.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM context_events").fetchone()[0]
            conn.execute("DELETE FROM context_events")
        return {"status": "reset", "deleted": int(count)}

    def fused_timeline(self, store: SQLiteMemory, limit: int = 100) -> dict[str, Any]:
        context = self.list_events(limit=limit)
        visual = store.timeline(limit=limit)
        items = []
        for item in visual:
            items.append({
                "timestamp": item["observed_at"], "modality": "vision",
                "event_type": "object_observation", "source": item["source"],
                "reference": item["track_id"], "summary": f'{item["label"]} (conf={item["confidence"]:.2f})'
            })
        for item in context:
            items.append({
                "timestamp": item["observed_at"], "modality": item["modality"],
                "event_type": item["event_type"], "source": item["source"],
                "reference": str(item["id"]), "summary": item["summary"]
            })
        items.sort(key=lambda x: x["timestamp"])
        return {"items": items[-limit:], "count": min(len(items), limit),
                "note": "Wspólna oś czasu porządkuje znaczniki czasu; nie potwierdza związku przyczynowego między zdarzeniami."}


def analyze_fusion(store: SQLiteMemory, context_memory: ContextMemory, window_seconds: int = 10) -> dict[str, Any]:
    """Build an explainable summary from recent visual observations and derived context events."""
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - window_seconds

    visual_recent = []
    for item in store.timeline(limit=500):
        try:
            stamp = parse_dt(item["observed_at"]).timestamp()
        except (TypeError, ValueError, KeyError):
            continue
        if cutoff <= stamp <= now.timestamp() + 2:
            visual_recent.append({
                "timestamp": item["observed_at"], "track_id": item["track_id"],
                "label": item["label"], "confidence": item["confidence"],
                "source": item["source"], "modality": "vision"
            })

    context_recent = []
    for item in context_memory.list_events(limit=500):
        try:
            stamp = parse_dt(item["observed_at"]).timestamp()
        except (TypeError, ValueError, KeyError):
            continue
        if cutoff <= stamp <= now.timestamp() + 2:
            context_recent.append({**item, "timestamp": item["observed_at"]})

    modality_counts: dict[str, int] = {}
    for item in visual_recent:
        modality_counts["vision"] = modality_counts.get("vision", 0) + 1
    for item in context_recent:
        modality_counts[item["modality"]] = modality_counts.get(item["modality"], 0) + 1

    modalities_present = sorted(modality_counts.keys())
    has_vision = bool(visual_recent)
    nonvisual = [e for e in context_recent if e["modality"] in {"audio", "text", "environment"}]
    has_multimodal_overlap = has_vision and bool(nonvisual)
    rules = [
        {
            "rule": "visual_activity_present", "matched": has_vision,
            "evidence_count": len(visual_recent),
            "description": "W oknie czasowym zapisano obserwacje wzrokowe."
        },
        {
            "rule": "nonvisual_context_present", "matched": bool(nonvisual),
            "evidence_count": len(nonvisual),
            "description": "W oknie czasowym zapisano pochodne zdarzenia audio, tekstowe lub środowiskowe."
        },
        {
            "rule": "temporal_multimodal_overlap", "matched": has_multimodal_overlap,
            "evidence_count": len(visual_recent) + len(nonvisual),
            "description": "Obserwacje wzrokowe i co najmniej jeden sygnał innej modalności wystąpiły w tym samym oknie."
        },
    ]

    correlations = []
    if has_vision:
        for event in nonvisual:
            event_dt = parse_dt(event["observed_at"])
            nearest = min(visual_recent, key=lambda obs: abs((parse_dt(obs["timestamp"]) - event_dt).total_seconds()))
            delta = abs((parse_dt(nearest["timestamp"]) - event_dt).total_seconds())
            if delta <= window_seconds:
                correlations.append({
                    "context_event_id": event["id"],
                    "context_modality": event["modality"],
                    "context_event_type": event["event_type"],
                    "context_source": event["source"],
                    "nearest_visual_track_id": nearest["track_id"],
                    "nearest_visual_label": nearest["label"],
                    "absolute_time_delta_seconds": round(delta, 3),
                    "interpretation": "Tylko zbieżność w czasie; nie oznacza, że widoczny obiekt jest źródłem dźwięku ani nadawcą wypowiedzi."
                })

    if len(modalities_present) >= 2 and has_multimodal_overlap:
        evidence_level = "multiple_modalities_temporally_aligned"
        summary = "W wybranym oknie zarejestrowano sygnały z wielu modalności."
    elif modalities_present:
        evidence_level = "single_modality_or_no_overlap"
        summary = "Dostępne są dane, ale nie ma wystarczających dowodów na zbieżność kilku modalności."
    else:
        evidence_level = "no_recent_evidence"
        summary = "Brak świeżych obserwacji w wybranym oknie."

    return {
        "window_seconds": window_seconds,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "evidence_level": evidence_level,
        "summary": summary,
        "modalities_present": modalities_present,
        "modality_counts": modality_counts,
        "visual_observations_in_window": len(visual_recent),
        "context_events_in_window": len(context_recent),
        "rules": rules,
        "temporal_correlations": correlations,
        "world_object_count": len(store.state()),
        "limitations": [
            "Fuzja jest regułowa i opiera się na znacznikach czasu, nie na modelu semantycznym.",
            "Sygnały korelujące czasowo nie muszą być przyczynowo powiązane.",
            "Moduł przechowuje tylko metadane/teksty zdarzeń, nie surowy dźwięk ani obraz.",
            "Treść summary może zawierać informacje wrażliwe; przed wysłaniem danych stosuj minimalizację i kontrolę dostępu."
        ]
    }
