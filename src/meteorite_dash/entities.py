import math
import random
from abc import ABC, abstractmethod
from collections.abc import Iterable

import pygame

from meteorite_dash.config import (
    ENEMY_SIZE,
    HUNTER_ENEMY_COLOR,
    HUNTER_ENEMY_SPEED,
    HUNTER_VERTICAL_SPEED,
    METEORITE_COLOR,
    METEORITE_RADIUS,
    METEORITE_SPEED,
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
    def draw(self, surface: pygame.Surface) -> None:
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


def _draw_left_triangle(surface: pygame.Surface, rect: pygame.Rect, color: Color) -> None:
    points = [(rect.left, rect.centery), (rect.right, rect.top), (rect.right, rect.bottom)]
    pygame.draw.polygon(surface, color, points)


def collides_with_any(player_rect: pygame.Rect, entities: Iterable[Entity]) -> bool:
    return any(player_rect.colliderect(entity.rect) for entity in entities)


def spawn_meteorite(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    sx: float = 1.0,
    su: float = 1.0,
) -> Meteorite:
    width, height = screen_size
    diameter = max(1, round(METEORITE_RADIUS * 2 * su))
    y = rng.randint(0, height - diameter)
    return Meteorite(pygame.Rect(width, y, diameter, diameter), METEORITE_SPEED * sx)


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
