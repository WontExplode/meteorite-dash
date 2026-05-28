from pathlib import Path

PACKAGE_DIR = Path(__file__).parent
ASSET_DIR = PACKAGE_DIR / "assets"
IMAGE_DIR = ASSET_DIR / "images"
SOUND_DIR = ASSET_DIR / "sounds"

SHIP_IMAGES = ("CopperShip1.png", "CopperShip3.png")


def image_path(filename: str) -> Path:
    return IMAGE_DIR / filename


def sound_path(filename: str) -> Path:
    return SOUND_DIR / filename
