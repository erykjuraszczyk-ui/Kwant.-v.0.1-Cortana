"""Walidacja obrazów i analiza bazowych cech pikseli."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Final

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS: Final[set[str]] = {"JPEG", "PNG", "WEBP"}
MAX_IMAGE_PIXELS: Final[int] = 20_000_000
THUMBNAIL_SIZE: Final[tuple[int, int]] = (512, 512)
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


class InvalidImageError(ValueError):
    """Obraz jest uszkodzony, nieobsługiwany lub przekracza limity."""


@dataclass(frozen=True)
class LoadedImage:
    """Otwarty obraz RGB wraz z metadanymi źródła; piksele pozostają w RAM."""

    image: Image.Image
    width: int
    height: int
    format: str
    mode: str


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


def load_validated_image(data: bytes) -> LoadedImage:
    """Bezpiecznie dekoduje JPEG/PNG/WEBP i zwraca kopię RGB bez pliku tymczasowego."""
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
            raw_width, raw_height = opened.size
            if raw_width <= 0 or raw_height <= 0:
                raise InvalidImageError("Obraz ma nieprawidłowe wymiary.")
            if raw_width * raw_height > MAX_IMAGE_PIXELS:
                raise InvalidImageError(
                    f"Obraz przekracza limit {MAX_IMAGE_PIXELS:,} pikseli."
                )
            original_mode = opened.mode
            corrected = ImageOps.exif_transpose(opened)
            rgb = corrected.convert("RGB")
            rgb.load()
            # Metadata must match the orientation used for detection and bounding boxes.
            width, height = rgb.size
            return LoadedImage(
                image=rgb,
                width=width,
                height=height,
                format=image_format,
                mode=original_mode,
            )
    except InvalidImageError:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
    ) as exc:
        raise InvalidImageError(
            "Plik nie jest poprawnym obrazem lub nie można go odczytać."
        ) from exc


def analyze_image(data: bytes) -> ImageFeatures:
    """Wylicza przybliżone cechy pikseli; nie identyfikuje semantycznie sceny."""
    loaded = load_validated_image(data)
    image = loaded.image.copy()
    image.thumbnail(THUMBNAIL_SIZE)
    count = image.width * image.height
    if count == 0:
        raise InvalidImageError("Nie udało się odczytać pikseli obrazu.")

    red = sum(image.getchannel("R").tobytes()) / count
    green = sum(image.getchannel("G").tobytes()) / count
    blue = sum(image.getchannel("B").tobytes()) / count
    brightness = (0.2126 * red + 0.7152 * green + 0.0722 * blue) / 255.0

    return ImageFeatures(
        width=loaded.width,
        height=loaded.height,
        format=loaded.format,
        mode=loaded.mode,
        mean_rgb={
            "red": round(red, 2),
            "green": round(green, 2),
            "blue": round(blue, 2),
        },
        brightness=round(brightness, 4),
        aspect_ratio=round(loaded.width / loaded.height, 4),
        pixel_count=loaded.width * loaded.height,
    )
