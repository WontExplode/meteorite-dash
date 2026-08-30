"""Asset-Pfade und gecachtes Laden von Bildern.

Pfade werden nur relativ zum Paket gebildet (`image_path`, `sound_path`);
`AssetLoader` cacht nach (Pfad, Größe, Rotation, Tint), damit nie pro Frame
geladen wird.
"""

from pathlib import Path

import pygame

from meteorite_dash.config import Color

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
    """Pfad eines generischen Sprites im Bilder-Ordner des Pakets."""
    return IMAGE_DIR / filename


def ship_image_path(filename: str) -> Path:
    """Pfad eines Schiffsbilds im ships-Unterordner."""
    return SHIP_IMAGE_DIR / filename


def sound_path(filename: str) -> Path:
    """Pfad einer Sound-/Musikdatei im Sounds-Ordner des Pakets."""
    return SOUND_DIR / filename


class AssetLoader:
    """Lädt skalierte Bilder (optional rotiert und getönt) mit kleinem Cache.

    `load_ship` lädt Schiffe aus dem ships-Ordner (rotiert, optional getönt),
    `load_image` generische Sprites wie Meteoriten.
    """

    def __init__(self) -> None:
        self._cache: dict[tuple[str, tuple[int, int], bool, Color | None], pygame.Surface] = {}

    def load_ship(
        self, filename: str, size: tuple[int, int], tint: Color | None = None
    ) -> pygame.Surface:
        """Schiffssprite in `size`, um 90 Grad nach links gedreht, optional getönt."""
        return self._load_image_from_path(
            ship_image_path(filename), size, rotate_left=True, tint=tint
        )

    def load_image(
        self,
        filename: str,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
    ) -> pygame.Surface:
        """Generisches Sprite (z. B. Meteorit) in `size`, optional nach links gedreht."""
        return self._load_image_from_path(image_path(filename), size, rotate_left=rotate_left)

    def _load_image_from_path(
        self,
        path: Path,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
        tint: Color | None = None,
    ) -> pygame.Surface:
        """Lädt, skaliert, rotiert und tönt ein Bild; Ergebnis landet im Cache."""
        key = (str(path), size, rotate_left, tint)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        image = pygame.image.load(path).convert_alpha()
        image = pygame.transform.scale(image, size)
        if rotate_left:
            image = pygame.transform.rotate(image, -90)
        if tint is not None:
            image.fill((*tint, 255), special_flags=pygame.BLEND_RGBA_MULT)
        self._cache[key] = image
        return image
