from pathlib import Path

import pygame

PACKAGE_DIR = Path(__file__).parent
ASSET_DIR = PACKAGE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
SHIP_IMAGE_DIR = IMAGE_DIR / "ships"
SOUND_DIR = ASSET_DIR / "sounds"

SHIP_IMAGES = (
    "CopperShip1.png",
    "CopperShip2.png",
    "CopperShip3.png",
    "CopperShip4.png",
    "CopperShip5.png",
    "CopperShip6.png",
    "CopperShip7.png",
    "EmeraldShip1.png",
    "EmeraldShip2.png",
    "EmeraldShip3.png",
    "EmeraldShip4.png",
    "EmeraldShip5.png",
    "EmeraldShip6.png",
    "EmeraldShip7.png",
    "GoldShip1.png",
    "GoldShip2.png",
    "GoldShip3.png",
    "GoldShip4.png",
    "GoldShip5.png",
    "GoldShip6.png",
    "GoldShip7.png",
)


def image_path(filename: str) -> Path:
    return IMAGE_DIR / filename


def ship_image_path(filename: str) -> Path:
    return SHIP_IMAGE_DIR / filename


def sound_path(filename: str) -> Path:
    return SOUND_DIR / filename


class AssetLoader:
    """Lädt skalierte Bilder mit kleinem Cache."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, int], bool], pygame.Surface] = {}

    def load_ship(self, filename: str, size: tuple[int, int]) -> pygame.Surface:
        return self._load_image_from_path(ship_image_path(filename), size, rotate_left=True)

    def load_image(
        self,
        filename: str,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
    ) -> pygame.Surface:
        return self._load_image_from_path(image_path(filename), size, rotate_left=rotate_left)

    def _load_image_from_path(
        self,
        path: Path,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
    ) -> pygame.Surface:
        key = (str(path), size, rotate_left)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        image = pygame.image.load(path).convert_alpha()
        image = pygame.transform.scale(image, size)
        if rotate_left:
            image = pygame.transform.rotate(image, -90)
        self._cache[key] = image
        return image
