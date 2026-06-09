from pathlib import Path

import pygame

from meteorite_dash.config import Color

PACKAGE_DIR = Path(__file__).parent
ASSET_DIR = PACKAGE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
SOUND_DIR = ASSET_DIR / "sounds"


def image_path(filename: str) -> Path:
    return IMAGE_DIR / filename


def sound_path(filename: str) -> Path:
    return SOUND_DIR / filename


class AssetLoader:
    """Loads ship images (scaled, rotated -90° and optionally tinted) with a small cache."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, int], Color | None], pygame.Surface] = {}

    def load_ship(
        self, filename: str, size: tuple[int, int], tint: Color | None = None
    ) -> pygame.Surface:
        key = (filename, size, tint)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        image = pygame.image.load(image_path(filename)).convert_alpha()
        image = pygame.transform.scale(image, size)
        image = pygame.transform.rotate(image, -90)
        if tint is not None:
            image.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = image
        return image
