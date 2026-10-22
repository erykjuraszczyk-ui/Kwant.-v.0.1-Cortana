"""Schematy odpowiedzi API PKK."""

from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str


class PerceptionEvent(BaseModel):
    event_id: str
    timestamp: datetime
    modality: Literal["image"] = "image"
    status: Literal["processed"] = "processed"
    method: str = "basic_pixel_statistics"
    note: str = "To analiza cech pikseli, a nie rozpoznawanie znaczenia sceny."
    features: dict[str, Any] = Field(default_factory=dict)
