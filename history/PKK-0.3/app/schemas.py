"""Modele walidacji odpowiedzi API PKK."""

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


class ImageMetadata(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    format: str
    source_mode: str


class BoundingBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float


class ObjectDetection(BaseModel):
    class_id: int = Field(ge=0)
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    bbox: BoundingBox


class ObjectDetectionEvent(BaseModel):
    event_id: str
    timestamp: datetime
    modality: Literal["image"] = "image"
    status: Literal["processed"] = "processed"
    method: str = "object_detection"
    model: str
    device: str
    confidence_threshold: float = Field(ge=0.0, le=1.0)
    processing_ms: float = Field(default=0.0, ge=0.0, description="Czas wywołania detektora w milisekundach; pierwsza analiza może obejmować ładowanie modelu.")
    image: ImageMetadata
    count: int = Field(ge=0)
    detections: list[ObjectDetection] = Field(default_factory=list)
    note: str = (
        "To predykcje modelu detekcji. Ocena confidence nie jest gwarancją "
        "poprawności ani skalibrowanym prawdopodobieństwem."
    )
