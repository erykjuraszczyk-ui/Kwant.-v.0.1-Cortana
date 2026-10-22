"""REST API PKK 0.3 — detekcja obiektów i percepcja klatek z kamery."""

from datetime import datetime, timezone
import logging
import os
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.perception.image_analyzer import (
    InvalidImageError,
    analyze_image,
    load_validated_image,
)
from app.perception.object_detector import (
    InferenceError,
    ModelUnavailableError,
    ObjectDetector,
)
from app.schemas import (
    HealthResponse,
    ImageMetadata,
    ObjectDetection,
    ObjectDetectionEvent,
    PerceptionEvent,
)

logging.basicConfig(level=os.getenv("PKK_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

SERVICE_NAME = "pkk-perception-api"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB

detector = ObjectDetector()

app = FastAPI(
    title="PKK — Percepcyjny Komputer Kwantowy",
    summary="Prototyp percepcji obrazu i detekcji obiektów z opcjonalnym podglądem kamery.",
    description=(
        "PKK 0.3 oferuje klasyczną detekcję obiektów YOLO oraz stronę do analizy "
        "obrazu z kamery w przeglądarce. Klipy i klatki nie są archiwizowane przez "
        "aplikację. Model działa na zwykłym CPU/GPU; ta wersja nie wykonuje "
        "obliczeń kwantowych."
    ),
    version=__version__,
)
app.state.detector = detector


def get_detector() -> ObjectDetector:
    """Dependency do łatwego podstawiania modelu w testach."""
    return app.state.detector


async def read_image_upload(file: UploadFile) -> bytes:
    """Odczytaj najwyżej limit + 1 bajt i zamknij upload niezależnie od wyniku."""
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
    finally:
        await file.close()
    if not content:
        raise HTTPException(status_code=400, detail="Przesłany plik jest pusty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Plik przekracza limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.",
        )
    return content


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "camera": "/camera",
    }


@app.get("/camera", include_in_schema=False)
def camera_page() -> FileResponse:
    """Interfejs przeglądarkowy. Dostęp do kamery wymaga zgody użytkownika."""
    page = Path(__file__).parent / "static" / "camera.html"
    return FileResponse(
        page,
        media_type="text/html",
        headers={"Cache-Control": "no-store"},
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Liveness: potwierdza, że API odpowiada, nie wymusza pobierania modelu."""
    return HealthResponse(status="ok", service=SERVICE_NAME, version=__version__)


@app.get("/version", tags=["system"])
def version() -> dict[str, str]:
    return {"service": SERVICE_NAME, "version": __version__}


@app.get("/perception/model", tags=["perception"], summary="Konfiguracja modelu")
def model_status(detector: ObjectDetector = Depends(get_detector)) -> dict[str, object]:
    """Zwraca stan konfiguracji bez ładowania modelu ani pobierania plików."""
    return {
        "model": detector.model_name,
        "device": detector.device,
        "confidence_threshold": detector.confidence,
        "max_detections": detector.max_detections,
        "loaded": detector.is_loaded,
        "note": "Model jest ładowany leniwie przy pierwszym żądaniu detekcji.",
    }


@app.post(
    "/perception/image",
    response_model=PerceptionEvent,
    tags=["perception"],
    summary="Analizuj podstawowe cechy obrazu",
)
async def perceive_image(file: UploadFile = File(...)) -> PerceptionEvent:
    """Zachowana zgodność z PKK 0.1: wylicza statystyki pikseli."""
    content = await read_image_upload(file)
    try:
        features = analyze_image(content)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PerceptionEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        method="basic_pixel_statistics",
        note="Statystyki pikseli nie identyfikują obiektów ani znaczenia sceny.",
        features=features.as_dict(),
    )


@app.post(
    "/perception/objects",
    response_model=ObjectDetectionEvent,
    tags=["perception"],
    summary="Wykryj obiekty na obrazie przy użyciu lokalnego modelu AI",
)
async def perceive_objects(
    file: UploadFile = File(...),
    confidence: float | None = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Opcjonalny próg confidence 0–1; wyższy próg zwykle daje mniej detekcji.",
    ),
    object_detector: ObjectDetector = Depends(get_detector),
) -> ObjectDetectionEvent:
    content = await read_image_upload(file)
    try:
        loaded = load_validated_image(content)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    used_threshold = object_detector.confidence if confidence is None else confidence
    started = perf_counter()
    try:
        detections = await run_in_threadpool(
            object_detector.detect, loaded.image, confidence
        )
    except ModelUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except InferenceError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return ObjectDetectionEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        method="ultralytics_yolo_object_detection",
        model=object_detector.model_name,
        device=object_detector.device,
        confidence_threshold=used_threshold,
        processing_ms=round((perf_counter() - started) * 1000.0, 2),
        image=ImageMetadata(
            width=loaded.width,
            height=loaded.height,
            format=loaded.format,
            source_mode=loaded.mode,
        ),
        count=len(detections),
        detections=[ObjectDetection(**item.as_dict()) for item in detections],
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Zwraca przewidywalny format błędów bez tracebacków w odpowiedzi."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
        headers=exc.headers,
    )
