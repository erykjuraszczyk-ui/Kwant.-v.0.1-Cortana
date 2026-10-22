"""Bezpieczna analiza bazowych cech obrazu; bez rozpoznawania semantycznego."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS: Final[set[str]] = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_PIXELS: Final[int] = 20_000_000
THUMBNAIL_SIZE: Final[tuple[int, int]] = (512, 512)

# Ochrona Pillow przed obrazami powodującymi nadmierne zużycie pamięci.
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class InvalidImageError(ValueError):
    """Obraz jest uszkodzony, nieobsługiwany lub przekracza limit pikseli."""


@dataclass(frozen=True)
class ImageFeatures:
    width: int
    height: int
    format: str
    mode: str
    mean_rgb: dict[str, float]
    brightness: float
    aspect_ratio: float
    pixel_count: int

    def as_dict(self) -> dict[str, object]:
        return {
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "mode": self.mode,
            "mean_rgb": self.mean_rgb,
            "brightness": self.brightness,
            "aspect_ratio": self.aspect_ratio,
            "pixel_count": self.pixel_count,
        }


def analyze_image(data: bytes) -> ImageFeatures:
    """Wylicza statystyki pikseli. Nie wykonuje OCR ani identyfikacji obiektów."""
    if not data:
        raise InvalidImageError("Przesłany plik jest pusty.")

    try:
        with Image.open(BytesIO(data)) as probe:
            image_format = (probe.format or "").upper()
            if image_format not in ALLOWED_FORMATS:
                raise InvalidImageError(
                    "Nieobsługiwany format. Dozwolone formaty: JPEG, PNG, WEBP."
                )
            probe.verify()

        with Image.open(BytesIO(data)) as opened:
            original_width, original_height = opened.size
            if original_width <= 0 or original_height <= 0:
                raise InvalidImageError("Obraz ma nieprawidłowe wymiary.")
            if original_width * original_height > MAX_IMAGE_PIXELS:
                raise InvalidImageError(
                    f"Obraz przekracza limit {MAX_IMAGE_PIXELS:,} pikseli."
                )

            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail(THUMBNAIL_SIZE)
            count = image.width * image.height
            if count == 0:
                raise InvalidImageError("Nie udało się odczytać pikseli obrazu.")

            # Operacje na bajtach ograniczają narzut pamięci i unikają listy krotek.
            red = sum(image.getchannel("R").tobytes()) / count
            green = sum(image.getchannel("G").tobytes()) / count
            blue = sum(image.getchannel("B").tobytes()) / count
            # Przybliżona luminancja sRGB, znormalizowana do przedziału 0–1.
            brightness = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0

            return ImageFeatures(
                width=original_width,
                height=original_height,
                format=image_format,
                mode=opened.mode,
                mean_rgb={
                    "red": round(red, 2),
                    "green": round(green, 2),
                    "blue": round(blue, 2),
                },
                brightness=round(brightness, 4),
                aspect_ratio=round(original_width / original_height, 4),
                pixel_count=original_width * original_height,
            )
    except InvalidImageError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise InvalidImageError("Plik nie jest poprawnym obrazem lub nie można go odczytać.") from exc
