from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class ObjectObservation(BaseModel):
    track_id: str = Field(min_length=1, max_length=96)
    label: str = Field(min_length=1, max_length=96)
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: list[float] = Field(min_length=4, max_length=4, description="[x1,y1,x2,y2], normalized 0..1")

    @field_validator("bbox")
    @classmethod
    def valid_bbox(cls, value):
        if any(v < 0 or v > 1 for v in value):
            raise ValueError("bbox coordinates must be in [0, 1]")
        if value[0] >= value[2] or value[1] >= value[3]:
            raise ValueError("bbox must satisfy x1 < x2 and y1 < y2")
        return value

class ObservationBatch(BaseModel):
    source: str = Field(min_length=1, max_length=96)
    observed_at: datetime = Field(default_factory=utc_now)
    observations: list[ObjectObservation] = Field(max_length=500)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value

class WorldObject(BaseModel):
    track_id: str
    label: str
    confidence: float
    bbox: list[float]
    source: str
    first_seen: datetime
    last_seen: datetime
    observations_count: int = 1
    status: Literal["active", "stale"] = "active"

class MemoryEvent(BaseModel):
    event_id: int
    event_type: Literal["object_first_seen", "object_updated", "object_missing", "memory_reset"]
    track_id: str | None = None
    label: str | None = None
    source: str | None = None
    timestamp: datetime = Field(default_factory=utc_now)
    details: dict = Field(default_factory=dict)
