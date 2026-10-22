from fastapi.testclient import TestClient

from app.main import app
from app.perception.object_detector import ModelUnavailableError

client = TestClient(app)


class FakeDetector:
    model_name = "fake-test-model.pt"
    device = "cpu"
    confidence = 0.25
    max_detections = 100
    is_loaded = True

    def __init__(self):
        self.last_confidence = None

    def detect(self, image, confidence=None):
        self.last_confidence = confidence
        return [
            type(
                "FakeDetection",
                (),
                {
                    "as_dict": lambda self: {
                        "class_id": 0,
                        "label": "person",
                        "confidence": 0.93,
                        "bbox": {"x1": 2.0, "y1": 3.0, "x2": 30.0, "y2": 40.0},
                    }
                },
            )()
        ]


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["version"] == "0.2.0"


def test_version_endpoint():
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json()["version"] == "0.2.0"


def test_pixel_statistics_endpoint_is_kept_for_compatibility(png_bytes):
    response = client.post(
        "/perception/image",
        files={"file": ("sample.png", png_bytes, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["method"] == "basic_pixel_statistics"
    assert body["features"]["width"] == 64
    assert body["features"]["height"] == 48


def test_object_detection_endpoint_formats_model_results(png_bytes):
    fake = FakeDetector()
    app.state.detector = fake
    response = client.post(
        "/perception/objects?confidence=0.5",
        files={"file": ("sample.png", png_bytes, "image/png")},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["method"] == "ultralytics_yolo_object_detection"
    assert body["model"] == "fake-test-model.pt"
    assert body["confidence_threshold"] == 0.5
    assert body["image"]["width"] == 64
    assert body["count"] == 1
    assert body["detections"][0]["label"] == "person"
    assert body["detections"][0]["bbox"]["x2"] == 30.0
    assert fake.last_confidence == 0.5


def test_object_detection_rejects_invalid_image():
    app.state.detector = FakeDetector()
    response = client.post(
        "/perception/objects",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert response.status_code == 400
    assert "error" in response.json()


def test_object_detection_rejects_out_of_range_confidence(png_bytes):
    app.state.detector = FakeDetector()
    response = client.post(
        "/perception/objects?confidence=1.5",
        files={"file": ("sample.png", png_bytes, "image/png")},
    )
    assert response.status_code == 422


def test_model_unavailable_returns_helpful_503(png_bytes):
    class UnavailableDetector(FakeDetector):
        def detect(self, image, confidence=None):
            raise ModelUnavailableError("Model unavailable in test")

    app.state.detector = UnavailableDetector()
    response = client.post(
        "/perception/objects",
        files={"file": ("sample.png", png_bytes, "image/png")},
    )
    assert response.status_code == 503
    assert response.json()["status_code"] == 503


def test_object_detection_rejects_upload_over_limit():
    # The API reads at most the limit plus one byte, so this tests the guard without image decoding.
    from app.main import MAX_UPLOAD_BYTES

    response = client.post(
        "/perception/objects",
        files={"file": ("large.png", b"x" * (MAX_UPLOAD_BYTES + 1), "image/png")},
    )
    assert response.status_code == 413
    assert response.json()["status_code"] == 413
