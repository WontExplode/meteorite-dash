"""Projektile der Spielerwaffen (Sim-Pfad, Referenzraum)."""

import pygame

from meteorite_dash.config import (
    PROJECTILE_COLOR,
    PROJECTILE_SIZE,
    PROJECTILE_SPEED,
    REFERENCE_SIZE,
)
from meteorite_dash.hitbox import solid_mask
from meteorite_dash.player import Player
from meteorite_dash.render import RenderContext


class Projectile:
    """Einfaches Projektil, das nach rechts fliegt (Referenzraum)."""

    def __init__(self, rect: pygame.Rect, speed_x: float, *, damage: int) -> None:
        self.rect = rect
        self._x = float(rect.x)
        self.speed_x = speed_x
        self.damage = damage

    @property
    def mask(self) -> pygame.mask.Mask:
        """Volle Fläche — das Projektil ist ein gefülltes Rechteck."""
        return solid_mask(self.rect.size)

    def update(self, dt: float) -> None:
        """Bewegt das Projektil dt-basiert nach rechts; Position float, `rect` gerundet."""
        self._x += self.speed_x * dt
        self.rect.x = round(self._x)

    @property
    def is_off_screen(self) -> bool:
        """True, sobald das Projektil den Referenzraum rechts verlassen hat."""
        return self.rect.left > REFERENCE_SIZE[0]

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet das Projektil als gefülltes Rechteck über den `RenderContext`."""
        pygame.draw.rect(ctx.surface, PROJECTILE_COLOR, ctx.rect(self.rect))

    def state_key(self) -> tuple[object, ...]:
        """Kanonischer Zustand für den Replay-Hash (Floats als `.hex()`)."""
        return (tuple(self.rect), self._x.hex(), self.speed_x.hex(), self.damage)


def spawn_projectile(player: Player, *, damage: int) -> Projectile:
    """Erzeugt ein Projektil an der rechten Kante des Spielers, vertikal zentriert."""
    width, height = PROJECTILE_SIZE
    x = player.rect.right
    y = player.rect.centery - height // 2
    return Projectile(pygame.Rect(x, y, width, height), PROJECTILE_SPEED, damage=damage)
