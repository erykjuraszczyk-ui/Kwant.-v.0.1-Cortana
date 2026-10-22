"""REST API starter dla Percepcyjnego Komputera Kwantowego (PKK) 0.1."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app import __version__
from app.perception.image_analyzer import InvalidImageError, analyze_image
from app.schemas import HealthResponse, PerceptionEvent

SERVICE_NAME = "pkk-perception-api"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MiB

app = FastAPI(
    title="PKK — Percepcyjny Komputer Kwantowy",
    summary="Prototyp API percepcji danych dla projektu PKK.",
    description=(
        "Wersja 0.1 przyjmuje obrazy i wylicza podstawowe cechy pikseli. "
        "Nie identyfikuje obiektów, nie przechowuje obrazów i nie łączy się z QPU."
    ),
    version=__version__,
)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=SERVICE_NAME, version=__version__)


@app.get("/version", tags=["system"])
def version() -> dict[str, str]:
    return {"service": SERVICE_NAME, "version": __version__}


@app.post(
    "/perception/image",
    response_model=PerceptionEvent,
    tags=["perception"],
    summary="Analizuj podstawowe cechy obrazu",
)
async def perceive_image(file: UploadFile = File(...)) -> PerceptionEvent:
    """Przetwarza obraz tylko w pamięci i zwraca statystyki pikseli."""
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()

    if not content:
        raise HTTPException(status_code=400, detail="Przesłany plik jest pusty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Plik przekracza limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MiB.",
        )

    try:
        features = analyze_image(content)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return PerceptionEvent(
        event_id=str(uuid4()),
        timestamp=datetime.now(timezone.utc),
        features=features.as_dict(),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    """Utrzymuje zwięzły i przewidywalny format błędów API."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
        headers=exc.headers,
    )
