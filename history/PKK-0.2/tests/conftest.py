from __future__ import annotations

from io import BytesIO

import pytest
from PIL import Image

from app.main import app


@pytest.fixture
def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 48), (80, 120, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(autouse=True)
def restore_detector():
    original = app.state.detector
    yield
    app.state.detector = original
