"""Adapter lokalnego detektora obiektów Ultralytics YOLO.

Import modelu jest opóźniony: API i testy podstawowe mogą wystartować bez ładowania
ciężkiego modelu. Przy pierwszym żądaniu detekcji biblioteka/model mogą zostać pobrane.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from threading import Lock
from typing import Any, Callable

from PIL import Image

logger = logging.getLogger(__name__)


class ModelUnavailableError(RuntimeError):
    """Modelu nie można załadować (np. brak zależności lub plików wag)."""


class InferenceError(RuntimeError):
    """Model został załadowany, ale wnioskowanie nie powiodło się."""


@dataclass(frozen=True)
class Detection:
    class_id: int
    label: str
    confidence: float
    bbox: dict[str, float]

    def as_dict(self) -> dict[str, Any]:
        return {
            "class_id": self.class_id,
            "label": self.label,
            "confidence": self.confidence,
            "bbox": self.bbox,
        }


class ObjectDetector:
    """Lazy-loaded, CPU-first adapter modelu YOLO.

    Parametr ``model_loader`` pozwala testować adapter bez sieci i bez prawdziwego
    modelu. W normalnym uruchomieniu importowany jest ``ultralytics.YOLO``.
    """

    def __init__(
        self,
        model_name: str | None = None,
        device: str | None = None,
        confidence: float | None = None,
        max_detections: int | None = None,
        model_loader: Callable[[str], Any] | None = None,
    ) -> None:
        self.model_name = model_name or os.getenv("PKK_MODEL", "yolo26n.pt")
        self.device = device or os.getenv("PKK_DEVICE", "cpu")
        self.confidence = self._read_confidence(confidence)
        self.max_detections = max_detections or int(
            os.getenv("PKK_MAX_DETECTIONS", "100")
        )
        if not 1 <= self.max_detections <= 300:
            raise ValueError("PKK_MAX_DETECTIONS musi mieścić się w zakresie 1–300.")
        self._model_loader = model_loader
        self._model: Any | None = None
        self._load_lock = Lock()
        self._inference_lock = Lock()

    @staticmethod
    def _read_confidence(value: float | None) -> float:
        try:
            confidence = (
                float(value)
                if value is not None
                else float(os.getenv("PKK_CONFIDENCE", "0.25"))
            )
        except ValueError as exc:
            raise ValueError("PKK_CONFIDENCE musi być liczbą od 0 do 1.") from exc
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("PKK_CONFIDENCE musi mieścić się w zakresie 0–1.")
        return confidence

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _get_model(self) -> Any:
        if self._model is not None:
            return self._model

        with self._load_lock:
            if self._model is not None:
                return self._model
            try:
                if self._model_loader is not None:
                    model = self._model_loader(self.model_name)
                else:
                    from ultralytics import YOLO  # Import dopiero przy pierwszej detekcji.

                    model = YOLO(self.model_name)
                self._model = model
            except Exception as exc:
                logger.exception("Nie udało się załadować modelu PKK (%s).", self.model_name)
                raise ModelUnavailableError(
                    "Nie udało się załadować modelu detekcji. Sprawdź instalację "
                    "zależności, nazwę PKK_MODEL oraz dostęp do internetu przy "
                    "pierwszym uruchomieniu. Szczegóły są w logu serwera."
                ) from exc
        return self._model

    @staticmethod
    def _class_name(names: Any, class_id: int) -> str:
        if isinstance(names, dict):
            return str(names.get(class_id, names.get(str(class_id), class_id)))
        if isinstance(names, (list, tuple)) and 0 <= class_id < len(names):
            return str(names[class_id])
        return str(class_id)

    def detect(
        self, image: Image.Image, confidence: float | None = None
    ) -> list[Detection]:
        """Zwraca etykiety, oceny modelu i prostokąty w pikselach obrazu."""
        threshold = self._read_confidence(confidence) if confidence is not None else self.confidence
        model = self._get_model()
        try:
            # Serializacja predykcji chroni współdzielony obiekt modelu przed
            # równoczesnymi wywołaniami z wielu żądań API.
            with self._inference_lock:
                results = model.predict(
                    source=image,
                    conf=threshold,
                    device=self.device,
                    verbose=False,
                    max_det=self.max_detections,
                )
            if not results:
                return []
            result = results[0]
            boxes = getattr(result, "boxes", None)
            if boxes is None:
                return []
            names = getattr(result, "names", {})
            detections: list[Detection] = []
            for box in boxes:
                class_id = int(box.cls.item())
                confidence_score = float(box.conf.item())
                coordinates = box.xyxy[0].tolist()
                if len(coordinates) != 4:
                    continue
                x1, y1, x2, y2 = (round(float(value), 2) for value in coordinates)
                detections.append(
                    Detection(
                        class_id=class_id,
                        label=self._class_name(names, class_id),
                        confidence=round(max(0.0, min(1.0, confidence_score)), 4),
                        bbox={"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                    )
                )
            return detections
        except ModelUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Błąd wnioskowania modelu PKK.")
            raise InferenceError(
                "Model nie ukończył analizy obrazu. Szczegóły są w logu serwera."
            ) from exc
