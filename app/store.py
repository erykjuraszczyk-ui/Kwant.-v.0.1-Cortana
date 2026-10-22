import json
import math
import os
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from .models import ObservationBatch, ObjectObservation

SCHEMA_VERSION = 1


def dt_to_str(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def bbox_center(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


class SQLiteMemory:
    """Thread-friendly SQLite store; each operation uses its own connection."""
    def __init__(self, path: str | None = None):
        raw = path or os.getenv("PKK_DB_PATH", "data/pkk.sqlite3")
        self.path = raw
        self.stale_after_seconds = max(0.1, float(os.getenv("PKK_STALE_AFTER_SECONDS", "5")))
        self.movement_threshold = max(0.0, float(os.getenv("PKK_MOVEMENT_THRESHOLD", "0.03")))
        self.max_objects = max(1, int(os.getenv("PKK_MAX_OBJECTS", "2000")))
        self.max_observations = max(100, int(os.getenv("PKK_MAX_OBSERVATIONS", "100000")))
        self.max_events = max(100, int(os.getenv("PKK_MAX_EVENTS", "20000")))
        if raw != ":memory:":
            Path(raw).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        if self.path == ":memory:":
            # A named shared-memory DB is needed across short-lived connections.
            raise ValueError("Use a file-backed SQLite path; :memory: is not supported by this store")
        conn = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def initialize(self) -> None:
        migrations = {
            1: [
                "CREATE TABLE IF NOT EXISTS world_objects (track_id TEXT PRIMARY KEY, label TEXT NOT NULL, confidence REAL NOT NULL, bbox_json TEXT NOT NULL, source TEXT NOT NULL, first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, observations_count INTEGER NOT NULL, status TEXT NOT NULL CHECK(status IN ('active','stale')))",
                "CREATE TABLE IF NOT EXISTS observations (id INTEGER PRIMARY KEY AUTOINCREMENT, track_id TEXT NOT NULL, label TEXT NOT NULL, confidence REAL NOT NULL, bbox_json TEXT NOT NULL, source TEXT NOT NULL, observed_at TEXT NOT NULL)",
                "CREATE INDEX IF NOT EXISTS idx_observations_track_time ON observations(track_id, observed_at)",
                "CREATE INDEX IF NOT EXISTS idx_observations_time ON observations(observed_at)",
                "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, track_id TEXT, label TEXT, source TEXT, timestamp TEXT NOT NULL, details_json TEXT NOT NULL)",
                "CREATE INDEX IF NOT EXISTS idx_events_time ON events(timestamp)",
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)",
            ]
        }
        with self.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
            current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations").fetchone()[0]
            for version in sorted(migrations):
                if version > current:
                    for sql in migrations[version]:
                        conn.execute(sql)
                    conn.execute("INSERT INTO schema_migrations(version, applied_at) VALUES(?, ?)", (version, dt_to_str(datetime.now(timezone.utc))))

    def _insert_event(self, conn, event_type: str, now: datetime, track_id=None, label=None, source=None, details=None):
        conn.execute(
            "INSERT INTO events(event_type, track_id, label, source, timestamp, details_json) VALUES(?,?,?,?,?,?)",
            (event_type, track_id, label, source, dt_to_str(now), json.dumps(details or {}, ensure_ascii=False)),
        )

    def _trim(self, conn) -> None:
        conn.execute("DELETE FROM observations WHERE id NOT IN (SELECT id FROM observations ORDER BY id DESC LIMIT ?)", (self.max_observations,))
        conn.execute("DELETE FROM events WHERE id NOT IN (SELECT id FROM events ORDER BY id DESC LIMIT ?)", (self.max_events,))

    def _mark_stale(self, conn, now: datetime) -> int:
        threshold = timedelta(seconds=self.stale_after_seconds)
        changed = 0
        rows = conn.execute("SELECT track_id, label, source, last_seen FROM world_objects WHERE status='active'").fetchall()
        for row in rows:
            try:
                age = now - parse_dt(row["last_seen"])
            except (ValueError, TypeError):
                continue
            if age > threshold:
                conn.execute("UPDATE world_objects SET status='stale' WHERE track_id=?", (row["track_id"],))
                self._insert_event(conn, "object_missing", now, row["track_id"], row["label"], row["source"], {"reason": "not_seen_recently", "age_seconds": round(age.total_seconds(), 3)})
                changed += 1
        return changed

    def ingest(self, batch: ObservationBatch) -> dict[str, Any]:
        now = batch.observed_at
        results = []
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for obs in batch.observations:
                row = conn.execute("SELECT * FROM world_objects WHERE track_id=?", (obs.track_id,)).fetchone()
                bbox_json = json.dumps(obs.bbox)
                conn.execute(
                    "INSERT INTO observations(track_id,label,confidence,bbox_json,source,observed_at) VALUES(?,?,?,?,?,?)",
                    (obs.track_id, obs.label, obs.confidence, bbox_json, batch.source, dt_to_str(now)),
                )
                if row is None:
                    count = conn.execute("SELECT COUNT(*) FROM world_objects").fetchone()[0]
                    if count >= self.max_objects:
                        oldest = conn.execute("SELECT track_id,label,source FROM world_objects ORDER BY last_seen ASC LIMIT 1").fetchone()
                        if oldest:
                            conn.execute("DELETE FROM world_objects WHERE track_id=?", (oldest["track_id"],))
                            self._insert_event(conn, "object_evicted", now, oldest["track_id"], oldest["label"], oldest["source"], {"reason": "capacity_limit"})
                    conn.execute("INSERT INTO world_objects VALUES(?,?,?,?,?,?,?,?,?)", (obs.track_id, obs.label, obs.confidence, bbox_json, batch.source, dt_to_str(now), dt_to_str(now), 1, "active"))
                    self._insert_event(conn, "object_entered", now, obs.track_id, obs.label, batch.source, {})
                    status = "active"
                    first_seen = now
                    count_obs = 1
                else:
                    old_bbox = json.loads(row["bbox_json"])
                    old_center, new_center = bbox_center(old_bbox), bbox_center(obs.bbox)
                    displacement = math.dist(old_center, new_center)
                    previously_stale = row["status"] == "stale"
                    label_changed = row["label"] != obs.label
                    if previously_stale:
                        self._insert_event(conn, "object_reappeared", now, obs.track_id, obs.label, batch.source, {"previous_status": "stale"})
                    elif label_changed:
                        self._insert_event(conn, "object_class_changed", now, obs.track_id, obs.label, batch.source, {"previous_label": row["label"], "new_label": obs.label})
                    elif displacement >= self.movement_threshold:
                        self._insert_event(conn, "object_moved", now, obs.track_id, obs.label, batch.source, {"center_displacement": round(displacement, 6), "from_center": old_center, "to_center": new_center})
                    first_seen = parse_dt(row["first_seen"])
                    count_obs = int(row["observations_count"]) + 1
                    status = "active"
                    conn.execute("UPDATE world_objects SET label=?, confidence=?, bbox_json=?, source=?, last_seen=?, observations_count=?, status='active' WHERE track_id=?", (obs.label, obs.confidence, bbox_json, batch.source, dt_to_str(now), count_obs, obs.track_id))
                results.append({"track_id": obs.track_id, "label": obs.label, "confidence": obs.confidence, "bbox": obs.bbox, "source": batch.source, "first_seen": dt_to_str(first_seen), "last_seen": dt_to_str(now), "observations_count": count_obs, "status": status})
            self._mark_stale(conn, now)
            self._trim(conn)
        return {"accepted": len(results), "objects": results}

    def state(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._mark_stale(conn, datetime.now(timezone.utc))
            rows = conn.execute("SELECT * FROM world_objects ORDER BY first_seen, track_id").fetchall()
        return [self._object_dict(r) for r in rows]

    def _object_dict(self, row) -> dict[str, Any]:
        return {"track_id": row["track_id"], "label": row["label"], "confidence": row["confidence"], "bbox": json.loads(row["bbox_json"]), "source": row["source"], "first_seen": row["first_seen"], "last_seen": row["last_seen"], "observations_count": row["observations_count"], "status": row["status"]}

    def events(self, limit: int = 100, since_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if since_id is None:
                rows = conn.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
                rows = list(reversed(rows))
            else:
                rows = conn.execute("SELECT * FROM events WHERE id>? ORDER BY id ASC LIMIT ?", (since_id, limit)).fetchall()
        return [{"id": r["id"], "event_type": r["event_type"], "track_id": r["track_id"], "label": r["label"], "source": r["source"], "timestamp": r["timestamp"], "details": json.loads(r["details_json"])} for r in rows]

    def timeline(self, track_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as conn:
            if track_id is None:
                rows = conn.execute("SELECT * FROM observations ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM observations WHERE track_id=? ORDER BY id DESC LIMIT ?", (track_id, limit)).fetchall()
        rows = list(reversed(rows))
        return [{"id": r["id"], "track_id": r["track_id"], "label": r["label"], "confidence": r["confidence"], "bbox": json.loads(r["bbox_json"]), "source": r["source"], "observed_at": r["observed_at"]} for r in rows]

    def stats(self) -> dict[str, Any]:
        with self.connect() as conn:
            objects = conn.execute("SELECT COUNT(*) FROM world_objects").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM world_objects WHERE status='active'").fetchone()[0]
            stale = conn.execute("SELECT COUNT(*) FROM world_objects WHERE status='stale'").fetchone()[0]
            observations = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
            events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            migration = conn.execute("SELECT COALESCE(MAX(version),0) FROM schema_migrations").fetchone()[0]
        return {"database": "sqlite", "schema_version": migration, "objects": objects, "active_objects": active, "stale_objects": stale, "observations": observations, "events": events}

    def reset(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM world_objects")
            conn.execute("DELETE FROM observations")
            conn.execute("DELETE FROM events")
            self._insert_event(conn, "memory_reset", now, details={"reason": "manual"})
        return {"status": "reset", "database": "sqlite"}
