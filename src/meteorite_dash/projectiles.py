import pygame

from meteorite_dash.config import PROJECTILE_COLOR, PROJECTILE_SIZE, PROJECTILE_SPEED
from meteorite_dash.player import Player


class Projectile:
    """Einfaches Projektil, das nach rechts fliegt."""

    def __init__(self, rect: pygame.Rect, speed_x: float, *, damage: int) -> None:
        self.rect = rect
        self._x = float(rect.x)
        self.speed_x = speed_x
        self.damage = damage

    def update(self, dt: float) -> None:
        self._x += self.speed_x * dt
        self.rect.x = round(self._x)

    def is_off_screen(self, screen_width: int) -> bool:
        return self.rect.left > screen_width

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, PROJECTILE_COLOR, self.rect)


def spawn_projectile(player: Player, *, damage: int, sx: float, su: float) -> Projectile:
    width = max(1, round(PROJECTILE_SIZE[0] * su))
    height = max(1, round(PROJECTILE_SIZE[1] * su))
    x = player.rect.right
    y = player.rect.centery - height // 2
    return Projectile(pygame.Rect(x, y, width, height), PROJECTILE_SPEED * sx, damage=damage)
