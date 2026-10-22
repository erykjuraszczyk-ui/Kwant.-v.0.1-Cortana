from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.main import app

client = TestClient(app)


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (10, 6), (20, 40, 60)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.1.0"


def test_version_endpoint():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == "0.1.0"


def test_perception_endpoint_returns_event_and_features():
    response = client.post(
        "/perception/image",
        files={"file": ("sample.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["modality"] == "image"
    assert body["status"] == "processed"
    assert body["features"]["width"] == 10
    assert body["features"]["height"] == 6
    assert len(body["event_id"]) > 10


def test_perception_endpoint_rejects_invalid_image():
    response = client.post(
        "/perception/image",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400
    assert "error" in response.json()
