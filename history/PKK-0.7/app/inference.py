"""Explainable, lightweight inference from recent object observations.

Predictions assume locally linear movement in normalized image coordinates.
They are short-horizon estimates, not guarantees of future position.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from .store import SQLiteMemory


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _center(bbox: list[float]) -> tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


def _linear_fit(times: list[float], values: list[float]) -> tuple[float, float, float]:
    """Return intercept, slope, and root-mean-square residual."""
    mean_t = sum(times) / len(times)
    mean_v = sum(values) / len(values)
    denominator = sum((t - mean_t) ** 2 for t in times)
    if denominator <= 1e-12:
        return values[-1], 0.0, 0.0
    slope = sum((t - mean_t) * (v - mean_v) for t, v in zip(times, values)) / denominator
    intercept = mean_v - slope * mean_t
    residuals = [v - (intercept + slope * t) for t, v in zip(times, values)]
    rmse = math.sqrt(sum(r * r for r in residuals) / len(residuals))
    return intercept, slope, rmse


def predict_track(memory: SQLiteMemory, track_id: str, horizon_seconds: float = 1.0,
                  limit: int = 30) -> dict[str, Any]:
    """Estimate a tracked object's next bbox using a linear fit of recent centers."""
    timeline = memory.timeline(track_id=track_id, limit=limit)
    if not timeline:
        return {"track_id": track_id, "status": "unavailable", "reason": "no_observations",
                "message": "Brak historii obserwacji dla tego identyfikatora."}

    # Deduplicate timestamps (multiple detections in one frame cannot establish velocity).
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in timeline:
        stamp = item["observed_at"]
        if stamp not in seen:
            ordered.append(item)
            seen.add(stamp)
    if len(ordered) < 2:
        return {"track_id": track_id, "status": "insufficient_data", "reason": "need_two_distinct_timestamps",
                "samples": len(ordered), "message": "Do wyznaczenia ruchu potrzebne są co najmniej dwie obserwacje w różnym czasie."}

    timestamps = [_parse_time(item["observed_at"]) for item in ordered]
    t0 = timestamps[0]
    times = [(stamp - t0).total_seconds() for stamp in timestamps]
    if max(times) <= 1e-6:
        return {"track_id": track_id, "status": "insufficient_data", "reason": "zero_time_span",
                "samples": len(ordered), "message": "Obserwacje nie obejmują wystarczającego odstępu czasu."}

    centers = [_center(item["bbox"]) for item in ordered]
    _, vx, rmse_x = _linear_fit(times, [p[0] for p in centers])
    _, vy, rmse_y = _linear_fit(times, [p[1] for p in centers])
    current = ordered[-1]
    current_bbox = current["bbox"]
    cx, cy = centers[-1]
    width = current_bbox[2] - current_bbox[0]
    height = current_bbox[3] - current_bbox[1]
    raw_cx = cx + vx * horizon_seconds
    raw_cy = cy + vy * horizon_seconds
    next_cx = min(max(raw_cx, width / 2), 1 - width / 2)
    next_cy = min(max(raw_cy, height / 2), 1 - height / 2)
    predicted_bbox = [
        round(next_cx - width / 2, 6), round(next_cy - height / 2, 6),
        round(next_cx + width / 2, 6), round(next_cy + height / 2, 6),
    ]
    span = max(times)
    rmse = math.hypot(rmse_x, rmse_y)
    if len(ordered) >= 5 and span >= 1.0 and rmse <= 0.02:
        quality = "high"
    elif len(ordered) >= 3 and span >= 0.3 and rmse <= 0.06:
        quality = "medium"
    else:
        quality = "low"

    return {
        "track_id": track_id,
        "status": "estimated",
        "method": "linear_regression_of_bbox_centers",
        "horizon_seconds": horizon_seconds,
        "samples": len(ordered),
        "observed_span_seconds": round(span, 4),
        "last_observed_at": current["observed_at"],
        "label": current["label"],
        "last_confidence": current["confidence"],
        "current_center": [round(cx, 6), round(cy, 6)],
        "predicted_center": [round(next_cx, 6), round(next_cy, 6)],
        "predicted_bbox": predicted_bbox,
        "velocity_normalized_per_second": [round(vx, 6), round(vy, 6)],
        "speed_normalized_per_second": round(math.hypot(vx, vy), 6),
        "fit_rmse": round(rmse, 6),
        "estimate_quality": quality,
        "caveat": "Zakłada ruch zbliżony do liniowego. Jakość nie jest prawdopodobieństwem; wynik nie gwarantuje przyszłej pozycji.",
    }


def summarize_recent_activity(memory: SQLiteMemory, window_seconds: int = 30) -> dict[str, Any]:
    """Apply transparent rules to recent event records and current world state."""
    now = datetime.now(timezone.utc)
    cutoff = now.timestamp() - window_seconds
    all_events = memory.events(limit=500)
    recent = []
    for event in all_events:
        try:
            stamp = _parse_time(event["timestamp"]).timestamp()
        except (KeyError, TypeError, ValueError):
            continue
        if cutoff <= stamp <= now.timestamp() + 5:
            recent.append(event)

    counts: dict[str, int] = {}
    by_type: dict[str, list[str]] = {}
    for event in recent:
        kind = event["event_type"]
        counts[kind] = counts.get(kind, 0) + 1
        if event.get("track_id"):
            by_type.setdefault(kind, []).append(event["track_id"])

    rules = [
        {"rule": "movement_observed", "matched": counts.get("object_moved", 0) > 0,
         "event_count": counts.get("object_moved", 0), "description": "W ostatnim oknie zapisano co najmniej jedno zdarzenie ruchu."},
        {"rule": "new_objects_observed", "matched": counts.get("object_entered", 0) > 0,
         "event_count": counts.get("object_entered", 0), "description": "W ostatnim oknie po raz pierwszy zauważono co najmniej jeden obiekt."},
        {"rule": "objects_missing_or_stale", "matched": counts.get("object_missing", 0) > 0,
         "event_count": counts.get("object_missing", 0), "description": "W ostatnim oknie obiekt przestał być obserwowany."},
        {"rule": "class_changes_observed", "matched": counts.get("object_class_changed", 0) > 0,
         "event_count": counts.get("object_class_changed", 0), "description": "W ostatnim oknie zmieniła się etykieta co najmniej jednego śledzonego obiektu."},
        {"rule": "objects_reappeared", "matched": counts.get("object_reappeared", 0) > 0,
         "event_count": counts.get("object_reappeared", 0), "description": "W ostatnim oknie ponownie zaobserwowano wcześniej nieaktywny obiekt."},
    ]
    objects = memory.state()
    return {
        "window_seconds": window_seconds,
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "recent_event_count": len(recent),
        "event_counts": counts,
        "rules": rules,
        "active_object_count": sum(1 for obj in objects if obj["status"] == "active"),
        "stale_object_count": sum(1 for obj in objects if obj["status"] == "stale"),
        "note": "Wnioski wynikają wyłącznie z zapisanych zdarzeń i reguł; nie są rozumieniem semantycznym ani gwarancją przyszłych zdarzeń.",
    }
