"""Pixelgenaue Hitboxen: Masken im Referenzraum statt Rechteck-Kollision.

Rechtecke kosten Leben, wo sich nur die Ecken zweier Boxen überschneiden — beim
Schiff (schmale Silhouette in einer 64x64-Box) und bei runden Meteoriten fällt
das deutlich auf. Deshalb trägt jedes kollidierende Objekt zusätzlich zu seiner
`rect` eine `mask`: den Alphakanal seines Sprites bzw. die Grundform, die es
zeichnet.

Masken entstehen **immer in Referenz-px** (`REFERENCE_SIZE`), nie in
Fenstergröße — Kollision bleibt damit fensterunabhängig und deterministisch:
dieselbe Asset-Datei plus dieselbe Zielgröße ergeben auf jedem Rechner dieselbe
Maske. Gebaut wird jede Maske einmal und dann gecacht; `pygame.image.load`
braucht dafür weder Display noch `pygame.init()`, `headless.run` bleibt also
headless.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pygame

from meteorite_dash.assets import image_path, ship_image_path

# Ab welchem Alphawert ein Pixel als „da“ gilt (pygame-Standard).
MASK_ALPHA_THRESHOLD = 127
_OPAQUE = (255, 255, 255, 255)

_MASK_CACHE: dict[tuple[object, ...], pygame.mask.Mask] = {}


class HasHitbox(Protocol):
    """Alles, was pixelgenau kollidiert: Rechteck plus gleich große Maske."""

    @property
    def rect(self) -> pygame.Rect:
        """Hitbox-Rechteck im Referenzraum."""

    @property
    def mask(self) -> pygame.mask.Mask:
        """Maske in der Größe von `rect`."""


@dataclass(frozen=True)
class Box:
    """Hitbox ohne eigenes Objekt — für Tests und Ad-hoc-Prüfungen."""

    rect: pygame.Rect
    mask: pygame.mask.Mask


def solid(rect: pygame.Rect) -> Box:
    """`Box` mit voll gefüllter Maske — verhält sich wie die alte Rechteck-Kollision."""
    return Box(rect, solid_mask(rect.size))


def overlaps(first: HasHitbox, second: HasHitbox) -> bool:
    """True, wenn sich die Masken beider Objekte in mindestens einem Pixel decken.

    Der Rechteck-Test läuft zuerst: er sortiert fast alle Paare aus, bevor die
    teurere Maskenprüfung nötig wird.
    """
    if not first.rect.colliderect(second.rect):
        return False
    offset = (second.rect.x - first.rect.x, second.rect.y - first.rect.y)
    return first.mask.overlap(second.mask, offset) is not None


def image_mask(filename: str, size: tuple[int, int]) -> pygame.mask.Mask:
    """Maske eines generischen Sprites (z. B. Meteorit) in Referenzgröße."""
    return _sprite_mask(image_path(filename), size, rotate_left=False)


def ship_mask(filename: str, size: tuple[int, int]) -> pygame.mask.Mask:
    """Maske eines Schiffssprites — wie `AssetLoader.load_ship` um 90 Grad gedreht."""
    return _sprite_mask(ship_image_path(filename), size, rotate_left=True)


def solid_mask(size: tuple[int, int]) -> pygame.mask.Mask:
    """Vollflächige Maske (Projektile, Pickups — sie füllen ihr Rechteck)."""
    key = ("solid", size)
    cached = _MASK_CACHE.get(key)
    if cached is None:
        cached = pygame.mask.Mask(size, fill=True)
        _MASK_CACHE[key] = cached
    return cached


def circle_mask(size: tuple[int, int]) -> pygame.mask.Mask:
    """Eingeschriebener Kreis — Münzen und Meteoriten ohne Sprite."""
    key = ("circle", size)
    cached = _MASK_CACHE.get(key)
    if cached is None:
        width, height = size
        surface = pygame.Surface(size, pygame.SRCALPHA)
        pygame.draw.circle(surface, _OPAQUE, (width // 2, height // 2), min(width, height) // 2)
        cached = pygame.mask.from_surface(surface, MASK_ALPHA_THRESHOLD)
        _MASK_CACHE[key] = cached
    return cached


def left_triangle_mask(size: tuple[int, int]) -> pygame.mask.Mask:
    """Nach links zeigendes Dreieck — die Silhouette, die Gegner zeichnen."""
    key = ("left_triangle", size)
    cached = _MASK_CACHE.get(key)
    if cached is None:
        width, height = size
        surface = pygame.Surface(size, pygame.SRCALPHA)
        points = [(0, height // 2), (width - 1, 0), (width - 1, height - 1)]
        pygame.draw.polygon(surface, _OPAQUE, points)
        cached = pygame.mask.from_surface(surface, MASK_ALPHA_THRESHOLD)
        _MASK_CACHE[key] = cached
    return cached


def _sprite_mask(path: Path, size: tuple[int, int], *, rotate_left: bool) -> pygame.mask.Mask:
    """Alphamaske eines Sprites in Referenzgröße, gecacht nach Pfad/Größe/Drehung.

    Bewusst ohne `convert_alpha()`: das bräuchte ein Display und würde die
    Simulation an ein Fenster koppeln.
    """
    key = ("sprite", str(path), size, rotate_left)
    cached = _MASK_CACHE.get(key)
    if cached is None:
        image = pygame.image.load(path)
        image = pygame.transform.scale(image, size)
        if rotate_left:
            image = pygame.transform.rotate(image, -90)
        cached = pygame.mask.from_surface(image, MASK_ALPHA_THRESHOLD)
        _MASK_CACHE[key] = cached
    return cached
