"""Explainable, policy-constrained decision engine for PKK 0.8."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field


class DecisionRequest(BaseModel):
    goal: str = Field(default="summarize_current_scene", min_length=1, max_length=160)
    horizon_seconds: int = Field(default=10, ge=1, le=300)
    include_context: bool = True


class DecisionItem(BaseModel):
    action: Literal["report", "observe_more", "no_action"]
    priority: Literal["low", "normal", "high"]
    rationale: str
    evidence: list[str]
    uncertainty: list[str]
    requires_human_approval: bool = False


def make_decision(store, context_memory, goal: str, horizon_seconds: int, include_context: bool) -> dict:
    """Produce a bounded recommendation; does not execute external actions."""
    now = datetime.now(timezone.utc)
    world = store.state()
    recent_context = context_memory.list_events(limit=200) if include_context else []
    # Context time filtering is explicit; ignore old events.
    cutoff = now.timestamp() - horizon_seconds
    recent_context = [
        e for e in recent_context
        if _parse_timestamp(e.get("observed_at")) is not None
        and cutoff <= _parse_timestamp(e["observed_at"]) <= now.timestamp() + 2
    ]

    active = [obj for obj in world if obj.get("status") == "active"]
    stale = [obj for obj in world if obj.get("status") == "stale"]
    evidence = []
    uncertainty = [
        "Wynik jest rekomendacją regułową, nie autonomiczną decyzją o skutkach zewnętrznych.",
        "Jakość zależy od danych wejściowych, identyfikatorów trackera i znaczników czasu."
    ]
    if active:
        labels = sorted({str(obj.get("label", "unknown")) for obj in active})
        evidence.append(f"Aktywne obiekty: {len(active)}; klasy: {', '.join(labels[:12])}.")
    else:
        evidence.append("Brak aktywnych obiektów w bieżącym modelu świata.")
    if stale:
        evidence.append(f"Obiekty oznaczone jako nieobserwowane: {len(stale)}.")
    if recent_context:
        counts = {}
        for event in recent_context:
            counts[event["modality"]] = counts.get(event["modality"], 0) + 1
        evidence.append("Świeże zdarzenia kontekstowe: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) + ".")
    else:
        evidence.append("Brak świeżych zdarzeń kontekstowych w wybranym oknie.")
    if not active and not recent_context:
        action, priority = "observe_more", "low"
        rationale = "Dane są niewystarczające do podsumowania sytuacji; zbierz kolejne obserwacje."
        uncertainty.append("Brak świeżych sygnałów nie oznacza, że w otoczeniu nic się nie dzieje.")
    else:
        action, priority = "report", "normal"
        rationale = f"Przygotuj podsumowanie obserwacji dla celu: {goal}."
    result = DecisionItem(
        action=action,
        priority=priority,
        rationale=rationale,
        evidence=evidence,
        uncertainty=uncertainty,
        requires_human_approval=False
    )
    return {
        "generated_at": now.isoformat().replace("+00:00", "Z"),
        "goal": goal,
        "action": result.action,
        "priority": result.priority,
        "rationale": result.rationale,
        "evidence": result.evidence,
        "uncertainty": result.uncertainty,
        "requires_human_approval": result.requires_human_approval,
        "execution": "none",
        "policy": {
            "external_actions_enabled": False,
            "destructive_actions_enabled": False,
            "human_approval_required_for_future_external_actions": True
        }
    }


def _parse_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.timestamp()
    except (TypeError, ValueError):
        return None
