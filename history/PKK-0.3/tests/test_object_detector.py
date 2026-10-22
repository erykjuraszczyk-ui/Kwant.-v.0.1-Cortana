from types import SimpleNamespace

from PIL import Image

from app.perception.object_detector import ObjectDetector


class FakeScalar:
    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


class FakeCoordinateRow:
    def tolist(self):
        return [1.25, 2.5, 30.75, 40.0]


class FakeCoordinates:
    def __getitem__(self, index):
        assert index == 0
        return FakeCoordinateRow()


class FakeBox:
    cls = FakeScalar(0)
    conf = FakeScalar(0.87654)
    xyxy = FakeCoordinates()


class FakeModel:
    def __init__(self):
        self.options = None

    def predict(self, **kwargs):
        self.options = kwargs
        return [SimpleNamespace(boxes=[FakeBox()], names={0: "person"})]


def test_detector_adapts_model_output_without_real_weights():
    fake_model = FakeModel()
    detector = ObjectDetector(
        model_name="mock-model.pt",
        model_loader=lambda name: fake_model,
        confidence=0.3,
    )
    detections = detector.detect(Image.new("RGB", (40, 50)), confidence=0.6)
    assert detector.is_loaded
    assert len(detections) == 1
    assert detections[0].label == "person"
    assert detections[0].class_id == 0
    assert detections[0].confidence == 0.8765
    assert detections[0].bbox == {"x1": 1.25, "y1": 2.5, "x2": 30.75, "y2": 40.0}
    assert fake_model.options["conf"] == 0.6
    assert fake_model.options["device"] == "cpu"


def test_detector_uses_lazy_loading():
    calls = []
    detector = ObjectDetector(
        model_name="mock-model.pt",
        model_loader=lambda name: calls.append(name) or FakeModel(),
    )
    assert detector.is_loaded is False
    detector.detect(Image.new("RGB", (40, 50)))
    assert calls == ["mock-model.pt"]
