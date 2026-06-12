import math
import random
from abc import ABC, abstractmethod
from collections.abc import Iterable

import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.config import (
    AMMO_PICKUP_COLOR,
    AMMO_PICKUP_SIZE,
    AMMO_PICKUP_SPEED,
    ENEMY_SIZE,
    HUNTER_ENEMY_COLOR,
    HUNTER_ENEMY_SPEED,
    HUNTER_VERTICAL_SPEED,
    METEORITE_COLOR,
    METEORITE_SPEED,
    METEORITE_VARIANTS,
    WAVE_AMPLITUDE,
    WAVE_ENEMY_COLOR,
    WAVE_ENEMY_SPEED,
    WAVE_FREQUENCY,
    Color,
)


class Entity(ABC):
    """Basis für alles, was von rechts nach links fliegt. `rect` ist die Hitbox."""

    def __init__(self, rect: pygame.Rect, speed_x: float) -> None:
        self.rect = rect
        self._x = float(rect.x)
        self._y = float(rect.y)
        self.speed_x = speed_x

    @property
    def damages_player(self) -> bool:
        return True

    @property
    def is_off_screen(self) -> bool:
        return self.rect.right < 0

    def update(self, dt: float, player_y: int) -> None:
        self._x -= self.speed_x * dt
        self._update_vertical(dt, player_y)
        self.rect.x = round(self._x)
        self.rect.y = round(self._y)

    def _update_vertical(self, dt: float, player_y: int) -> None:  # noqa: B027  (optional hook)
        """Standard: keine vertikale Bewegung; Subklassen überschreiben dies."""

    @abstractmethod
    def draw(self, surface: pygame.Surface) -> None:
        raise NotImplementedError


class Meteorite(Entity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        image: pygame.Surface | None = None,
    ) -> None:
        super().__init__(rect, speed_x)
        self.image = image

    def draw(self, surface: pygame.Surface) -> None:
        if self.image is not None:
            surface.blit(self.image, self.rect)
            return

        radius = max(1, self.rect.width // 2)
        pygame.draw.circle(surface, METEORITE_COLOR, self.rect.center, radius)


class WaveEnemy(Entity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        amplitude: float = WAVE_AMPLITUDE,
        frequency: float = WAVE_FREQUENCY,
    ) -> None:
        super().__init__(rect, speed_x)
        self._base_y = self._y
        self._elapsed = 0.0
        self._amplitude = amplitude
        self._frequency = frequency

    def _update_vertical(self, dt: float, player_y: int) -> None:
        self._elapsed += dt
        self._y = self._base_y + self._amplitude * math.sin(
            2 * math.pi * self._frequency * self._elapsed
        )

    def draw(self, surface: pygame.Surface) -> None:
        _draw_left_triangle(surface, self.rect, WAVE_ENEMY_COLOR)


class HunterEnemy(Entity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        vertical_speed: float = HUNTER_VERTICAL_SPEED,
    ) -> None:
        super().__init__(rect, speed_x)
        self._vertical_speed = vertical_speed

    def _update_vertical(self, dt: float, player_y: int) -> None:
        target = player_y - self.rect.height / 2  # Ziel-top, damit Center auf player_y zielt
        step = self._vertical_speed * dt
        if abs(target - self._y) <= step:
            self._y = target
        elif target > self._y:
            self._y += step
        else:
            self._y -= step

    def draw(self, surface: pygame.Surface) -> None:
        _draw_left_triangle(surface, self.rect, HUNTER_ENEMY_COLOR)


class AmmoPickup(Entity):
    @property
    def damages_player(self) -> bool:
        return False

    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, AMMO_PICKUP_COLOR, self.rect, border_radius=4)
        inner = self.rect.inflate(-self.rect.width // 3, -self.rect.height // 3)
        pygame.draw.rect(surface, (255, 240, 180), inner, border_radius=2)


def _draw_left_triangle(surface: pygame.Surface, rect: pygame.Rect, color: Color) -> None:
    points = [(rect.left, rect.centery), (rect.right, rect.top), (rect.right, rect.bottom)]
    pygame.draw.polygon(surface, color, points)


def collides_with_any(player_rect: pygame.Rect, entities: Iterable[Entity]) -> bool:
    return any(
        entity.damages_player and player_rect.colliderect(entity.rect) for entity in entities
    )


def collect_pickups(player_rect: pygame.Rect, entities: list[Entity]) -> list[Entity]:
    """Entfernt eingesammelte Munitions-Pickups und gibt sie zurück."""
    collected: list[Entity] = []
    remaining: list[Entity] = []
    for entity in entities:
        if isinstance(entity, AmmoPickup) and player_rect.colliderect(entity.rect):
            collected.append(entity)
        else:
            remaining.append(entity)
    entities[:] = remaining
    return collected


def spawn_meteorite(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    sx: float = 1.0,
    su: float = 1.0,
    assets: AssetLoader | None = None,
) -> Meteorite:
    width, height = screen_size
    variant = rng.choice(METEORITE_VARIANTS)
    diameter = max(1, round(variant.radius * 2 * su))
    image_filename = rng.choice(variant.images)
    image = assets.load_image(image_filename, (diameter, diameter)) if assets is not None else None
    y = rng.randint(0, max(0, height - diameter))
    return Meteorite(pygame.Rect(width, y, diameter, diameter), METEORITE_SPEED * sx, image)


def spawn_wave_enemy(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    sx: float = 1.0,
    sy: float = 1.0,
    su: float = 1.0,
) -> WaveEnemy:
    width, height = screen_size
    w = max(1, round(ENEMY_SIZE[0] * su))
    h = max(1, round(ENEMY_SIZE[1] * su))
    y = rng.randint(0, height - h)
    return WaveEnemy(
        pygame.Rect(width, y, w, h),
        WAVE_ENEMY_SPEED * sx,
        amplitude=WAVE_AMPLITUDE * sy,
    )


def spawn_hunter_enemy(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    sx: float = 1.0,
    sy: float = 1.0,
    su: float = 1.0,
) -> HunterEnemy:
    width, height = screen_size
    w = max(1, round(ENEMY_SIZE[0] * su))
    h = max(1, round(ENEMY_SIZE[1] * su))
    y = rng.randint(0, height - h)
    return HunterEnemy(
        pygame.Rect(width, y, w, h),
        HUNTER_ENEMY_SPEED * sx,
        vertical_speed=HUNTER_VERTICAL_SPEED * sy,
    )


def spawn_ammo_pickup(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    sx: float = 1.0,
    su: float = 1.0,
) -> AmmoPickup:
    width, height = screen_size
    w = max(1, round(AMMO_PICKUP_SIZE[0] * su))
    h = max(1, round(AMMO_PICKUP_SIZE[1] * su))
    y = rng.randint(0, max(0, height - h))
    return AmmoPickup(pygame.Rect(width, y, w, h), AMMO_PICKUP_SPEED * sx)
