"""Render-Kontext: bildet den Referenzraum der Simulation auf das Fenster ab.

Die Spiellogik rechnet ausschließlich im 800x600-Referenzraum (`REFERENCE_SIZE`).
Erst beim Zeichnen werden Rechtecke über den `Viewport` in Fensterpixel
übersetzt. Entities halten deshalb keine Surfaces — Bilder kommen hier aus dem
`AssetLoader`-Cache in genau der Größe, die das Fenster gerade braucht.
"""

from dataclasses import dataclass

import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.viewport import Viewport


@dataclass(frozen=True)
class RenderContext:
    """Zeichenziel plus `Viewport`; wird jedem `draw(ctx)` übergeben."""

    surface: pygame.Surface
    viewport: Viewport
    # Ohne Loader (Tests) zeichnen Entities ihre Fallback-Formen.
    assets: AssetLoader | None = None
    # Erschütterung in Referenz-px (`effects.Effects.offset`): verschiebt alles,
    # was durch diesen Kontext gezeichnet wird — HUD-Code umgeht ihn bewusst.
    offset: tuple[float, float] = (0.0, 0.0)

    def rect(self, ref: pygame.Rect) -> pygame.Rect:
        """Referenz-Rechteck -> Fenster: Position pro Achse gestreckt, Größe höhen-gebunden."""
        vp = self.viewport
        offset_x, offset_y = self.offset
        return pygame.Rect(
            vp.px(ref.x + offset_x),
            vp.py(ref.y + offset_y),
            max(1, vp.s(ref.width)),
            max(1, vp.s(ref.height)),
        )

    def point(self, ref_x: float, ref_y: float) -> tuple[int, int]:
        """Referenzpunkt -> Fensterkoordinate, inklusive Erschütterung."""
        offset_x, offset_y = self.offset
        return self.viewport.point(ref_x + offset_x, ref_y + offset_y)

    def image(self, filename: str, size: tuple[int, int]) -> pygame.Surface | None:
        """Sprite in Fenstergröße aus dem Asset-Cache; None ohne Loader (Fallback-Form)."""
        if self.assets is None:
            return None
        return self.assets.load_image(filename, size)
