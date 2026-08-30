"""Viewport: Abbildung des 800x600-Referenzraums auf das echte Fenster.

Positionen werden pro Achse gestreckt, Größen und Schriften einheitlich
höhen-gebunden skaliert. Bei `REFERENCE_SIZE` ist alles Identität.
"""

import pygame

from meteorite_dash.config import MENU_FONT_NAME, REFERENCE_SIZE

REF_W, REF_H = REFERENCE_SIZE


class Viewport:
    """Maps reference-space coordinates and sizes onto the live window.

    The window *is* the play area (fully fluid, edge-to-edge, no letterbox).
    Per-axis factors ``scale_x`` / ``scale_y`` stretch positions to fill the
    window, while a single height-tied ``scale`` keeps sprites, speeds and fonts
    proportional without distortion. At ``REFERENCE_SIZE`` every factor is exactly
    ``1.0`` and all helpers are identity functions, so behaviour is byte-identical
    to the original fixed-size game.
    """

    def __init__(self, width: int, height: int) -> None:
        self._width = width
        self._height = height
        self._font_cache: dict[int, pygame.font.Font] = {}

    @property
    def width(self) -> int:
        """Fensterbreite in Pixeln."""
        return self._width

    @property
    def height(self) -> int:
        """Fensterhöhe in Pixeln."""
        return self._height

    @property
    def size(self) -> tuple[int, int]:
        """Fenstergröße als (Breite, Höhe)."""
        return (self._width, self._height)

    @property
    def center_x(self) -> int:
        """Horizontale Fenstermitte in Pixeln."""
        return self._width // 2

    def resize(self, width: int, height: int) -> None:
        """Übernimmt die neue Fenstergröße; der Font-Cache bleibt gültig (Key = Pixelgröße)."""
        self._width = width
        self._height = height

    # --- scale factors ----------------------------------------------------

    @property
    def scale_x(self) -> float:
        """Streckfaktor der x-Achse (Fensterbreite / Referenzbreite)."""
        return self._width / REF_W

    @property
    def scale_y(self) -> float:
        """Streckfaktor der y-Achse (Fensterhöhe / Referenzhöhe)."""
        return self._height / REF_H

    @property
    def scale(self) -> float:
        """Uniform factor for sizes, speeds and fonts (height-tied).

        The player moves only vertically and enemies cross horizontally at a
        px/second speed, so tying size and speed to the height axis keeps the
        vertical dodge difficulty invariant across window shapes and never
        distorts circular meteorites. ``min(scale_x, scale_y)`` would shrink
        sprites on a wide-but-short window even though the limiting (height)
        axis did not change; a geometric mean would couple vertical dodge
        difficulty to horizontal window size for no gameplay reason.
        """
        return self.scale_y

    # --- reference-space -> screen mappers --------------------------------

    def px(self, ref_x: float) -> int:
        """Map a reference x-coordinate to a screen x (stretched, edge-to-edge)."""
        return round(ref_x * self.scale_x)

    def py(self, ref_y: float) -> int:
        """Map a reference y-coordinate to a screen y (stretched, edge-to-edge)."""
        return round(ref_y * self.scale_y)

    def point(self, ref_x: float, ref_y: float) -> tuple[int, int]:
        """Referenzpunkt als Fensterkoordinate (`px`, `py`)."""
        return (self.px(ref_x), self.py(ref_y))

    def s(self, ref_value: float) -> int:
        """Scale a size or pixel length uniformly (height-tied)."""
        return round(ref_value * self.scale)

    def font_size(self, ref_size: int) -> int:
        """Uniformly scaled, clamped font size (pygame fonts need size >= 1)."""
        return max(1, round(ref_size * self.scale))

    def font(self, ref_size: int) -> pygame.font.Font:
        """Return a SysFont scaled to the viewport, cached by pixel size.

        SysFont is comparatively expensive, so a Font is built only the first
        time a given pixel size is needed (e.g. after a resize), never per frame.
        """
        size = self.font_size(ref_size)
        font = self._font_cache.get(size)
        if font is None:
            font = pygame.font.SysFont(MENU_FONT_NAME, size)
            self._font_cache[size] = font
        return font
