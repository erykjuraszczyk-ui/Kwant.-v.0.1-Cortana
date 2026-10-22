from io import BytesIO

from PIL import Image
import pytest

from app.perception.image_analyzer import InvalidImageError, analyze_image


def make_png(color=(255, 0, 0), size=(12, 8)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_analyze_red_png_returns_basic_features():
    result = analyze_image(make_png())
    assert result.width == 12
    assert result.height == 8
    assert result.format == "PNG"
    assert result.mean_rgb == {"red": 255.0, "green": 0.0, "blue": 0.0}
    assert result.aspect_ratio == 1.5
    assert 0 <= result.brightness <= 1


def test_empty_input_is_rejected():
    with pytest.raises(InvalidImageError, match="pusty"):
        analyze_image(b"")


def test_non_image_input_is_rejected():
    with pytest.raises(InvalidImageError):
        analyze_image(b"to nie jest obraz")


def test_svg_is_not_allowed():
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"></svg>'
    with pytest.raises(InvalidImageError):
        analyze_image(svg)
