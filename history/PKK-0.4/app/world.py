from collections import deque
from datetime import datetime, timezone, timedelta
from threading import RLock
from .models import ObservationBatch, WorldObject, MemoryEvent

class WorldMemory:
    def __init__(self, max_objects: int = 1000, max_events: int = 2000, stale_after_seconds: float = 5.0):
        self.max_objects = max_objects
        self.events = deque(maxlen=max_events)
        self.objects: dict[str, WorldObject] = {}
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self._next_event_id = 1
        self._lock = RLock()

    def _event(self, event_type, track_id=None, label=None, source=None, details=None, timestamp=None):
        event = MemoryEvent(
            event_id=self._next_event_id,
            event_type=event_type,
            track_id=track_id,
            label=label,
            source=source,
            details=details or {},
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        self._next_event_id += 1
        self.events.append(event)
        return event

    def ingest(self, batch: ObservationBatch):
        results = []
        with self._lock:
            now = batch.observed_at
            for obs in batch.observations:
                old = self.objects.get(obs.track_id)
                if old is None:
                    if len(self.objects) >= self.max_objects:
                        oldest_key = min(self.objects, key=lambda k: self.objects[k].last_seen)
                        removed = self.objects.pop(oldest_key)
                        self._event("object_missing", removed.track_id, removed.label, removed.source,
                                    {"reason": "capacity_eviction"}, now)
                    item = WorldObject(
                        track_id=obs.track_id, label=obs.label, confidence=obs.confidence,
                        bbox=obs.bbox, source=batch.source, first_seen=now, last_seen=now,
                        observations_count=1, status="active"
                    )
                    self.objects[obs.track_id] = item
                    self._event("object_first_seen", obs.track_id, obs.label, batch.source, {}, now)
                else:
                    item = WorldObject(
                        track_id=obs.track_id, label=obs.label, confidence=obs.confidence,
                        bbox=obs.bbox, source=batch.source, first_seen=old.first_seen,
                        last_seen=now, observations_count=old.observations_count + 1,
                        status="active"
                    )
                    self.objects[obs.track_id] = item
                    self._event("object_updated", obs.track_id, obs.label, batch.source,
                                {"observations_count": item.observations_count}, now)
                results.append(item)
            self._mark_stale(now)
        return {"accepted": len(results), "objects": results}

    def _mark_stale(self, now):
        for key, obj in list(self.objects.items()):
            if obj.status == "active" and now - obj.last_seen > self.stale_after:
                self.objects[key] = obj.model_copy(update={"status": "stale"})
                self._event("object_missing", obj.track_id, obj.label, obj.source,
                            {"reason": "not_seen_recently"}, now)

    def state(self):
        with self._lock:
            return [obj.model_dump(mode="json") for obj in self.objects.values()]

    def event_list(self, limit=100):
        with self._lock:
            return [event.model_dump(mode="json") for event in list(self.events)[-limit:]]

    def reset(self):
        with self._lock:
            self.objects.clear()
            self.events.clear()
            self._next_event_id = 1
            self._event("memory_reset", details={"reason": "manual"})
            return {"status": "reset"}
