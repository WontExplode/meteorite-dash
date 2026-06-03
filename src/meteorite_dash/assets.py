from pathlib import Path

import pygame

PACKAGE_DIR = Path(__file__).parent
ASSET_DIR = PACKAGE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
SOUND_DIR = ASSET_DIR / "sounds"

SHIP_IMAGES = ("CopperShip1.png", "CopperShip3.png")


def image_path(filename: str) -> Path:
    return IMAGE_DIR / filename


def sound_path(filename: str) -> Path:
    return SOUND_DIR / filename


class AssetLoader:
    """Lädt skalierte Bilder mit kleinem Cache."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, int], bool], pygame.Surface] = {}

    def load_ship(self, filename: str, size: tuple[int, int]) -> pygame.Surface:
        return self.load_image(filename, size, rotate_left=True)

    def load_image(
        self,
        filename: str,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
    ) -> pygame.Surface:
        key = (filename, size, rotate_left)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        image = pygame.image.load(image_path(filename)).convert_alpha()
        image = pygame.transform.scale(image, size)
        if rotate_left:
            image = pygame.transform.rotate(image, -90)
        self._cache[key] = image
        return image
