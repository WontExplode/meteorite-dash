import pygame

from meteorite_dash.config import (
    PROJECTILE_COLOR,
    PROJECTILE_SIZE,
    PROJECTILE_SPEED,
    REFERENCE_SIZE,
)
from meteorite_dash.player import Player
from meteorite_dash.render import RenderContext


class Projectile:
    """Einfaches Projektil, das nach rechts fliegt (Referenzraum)."""

    def __init__(self, rect: pygame.Rect, speed_x: float, *, damage: int) -> None:
        self.rect = rect
        self._x = float(rect.x)
        self.speed_x = speed_x
        self.damage = damage

    def update(self, dt: float) -> None:
        self._x += self.speed_x * dt
        self.rect.x = round(self._x)

    @property
    def is_off_screen(self) -> bool:
        return self.rect.left > REFERENCE_SIZE[0]

    def draw(self, ctx: RenderContext) -> None:
        pygame.draw.rect(ctx.surface, PROJECTILE_COLOR, ctx.rect(self.rect))


def spawn_projectile(player: Player, *, damage: int) -> Projectile:
    width, height = PROJECTILE_SIZE
    x = player.rect.right
    y = player.rect.centery - height // 2
    return Projectile(pygame.Rect(x, y, width, height), PROJECTILE_SPEED, damage=damage)
