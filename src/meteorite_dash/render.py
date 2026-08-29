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
    surface: pygame.Surface
    viewport: Viewport
    # Ohne Loader (Tests) zeichnen Entities ihre Fallback-Formen.
    assets: AssetLoader | None = None

    def rect(self, ref: pygame.Rect) -> pygame.Rect:
        """Referenz-Rechteck -> Fenster: Position pro Achse gestreckt, Größe höhen-gebunden."""
        vp = self.viewport
        return pygame.Rect(
            vp.px(ref.x),
            vp.py(ref.y),
            max(1, vp.s(ref.width)),
            max(1, vp.s(ref.height)),
        )

    def image(self, filename: str, size: tuple[int, int]) -> pygame.Surface | None:
        if self.assets is None:
            return None
        return self.assets.load_image(filename, size)
