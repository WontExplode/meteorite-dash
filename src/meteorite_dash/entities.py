import math
import random
from abc import ABC, abstractmethod
from collections.abc import Iterable

import pygame

from meteorite_dash.config import (
    AMMO_PICKUP_COLOR,
    AMMO_PICKUP_HIGHLIGHT_COLOR,
    AMMO_PICKUP_SIZE,
    AMMO_PICKUP_SPEED,
    ENEMY_SIZE,
    HUNTER_ENEMY_COLOR,
    HUNTER_ENEMY_CONTACT_DAMAGE,
    HUNTER_ENEMY_HP,
    HUNTER_ENEMY_SPEED,
    HUNTER_VERTICAL_SPEED,
    METEORITE_COLOR,
    METEORITE_SPEED,
    METEORITE_VARIANTS,
    WAVE_AMPLITUDE,
    WAVE_ENEMY_COLOR,
    WAVE_ENEMY_CONTACT_DAMAGE,
    WAVE_ENEMY_HP,
    WAVE_ENEMY_SPEED,
    WAVE_FREQUENCY,
    Color,
)
from meteorite_dash.render import RenderContext


class Entity(ABC):
    """Basis für alles, was von rechts nach links fliegt. `rect` ist die Hitbox.

    Alle Koordinaten liegen im Referenzraum (`REFERENCE_SIZE`); erst `draw`
    übersetzt über den `RenderContext` ins Fenster.
    """

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
    def draw(self, ctx: RenderContext) -> None:
        raise NotImplementedError


class DamageableEntity(Entity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        hp: int,
        contact_damage: int,
    ) -> None:
        super().__init__(rect, speed_x)
        self.max_hp = hp
        self.hp = hp
        self.contact_damage = contact_damage

    def take_damage(self, amount: int) -> bool:
        self.hp -= amount
        return self.hp <= 0


class Meteorite(DamageableEntity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        image_name: str | None = None,
        *,
        hp: int,
        contact_damage: int,
    ) -> None:
        super().__init__(rect, speed_x, hp=hp, contact_damage=contact_damage)
        # Nur der Dateiname: die Surface holt der RenderContext in Fenstergröße.
        self.image_name = image_name

    def draw(self, ctx: RenderContext) -> None:
        target = ctx.rect(self.rect)
        image = ctx.image(self.image_name, target.size) if self.image_name else None
        if image is not None:
            ctx.surface.blit(image, target)
            return

        radius = max(1, target.width // 2)
        pygame.draw.circle(ctx.surface, METEORITE_COLOR, target.center, radius)


class WaveEnemy(DamageableEntity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        hp: int = WAVE_ENEMY_HP,
        contact_damage: int = WAVE_ENEMY_CONTACT_DAMAGE,
        amplitude: float = WAVE_AMPLITUDE,
        frequency: float = WAVE_FREQUENCY,
    ) -> None:
        super().__init__(rect, speed_x, hp=hp, contact_damage=contact_damage)
        self._base_y = self._y
        self._elapsed = 0.0
        self._amplitude = amplitude
        self._frequency = frequency

    def _update_vertical(self, dt: float, player_y: int) -> None:
        self._elapsed += dt
        self._y = self._base_y + self._amplitude * math.sin(
            2 * math.pi * self._frequency * self._elapsed
        )

    def draw(self, ctx: RenderContext) -> None:
        _draw_left_triangle(ctx.surface, ctx.rect(self.rect), WAVE_ENEMY_COLOR)


class HunterEnemy(DamageableEntity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        hp: int = HUNTER_ENEMY_HP,
        contact_damage: int = HUNTER_ENEMY_CONTACT_DAMAGE,
        vertical_speed: float = HUNTER_VERTICAL_SPEED,
    ) -> None:
        super().__init__(rect, speed_x, hp=hp, contact_damage=contact_damage)
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

    def draw(self, ctx: RenderContext) -> None:
        _draw_left_triangle(ctx.surface, ctx.rect(self.rect), HUNTER_ENEMY_COLOR)


class AmmoPickup(Entity):
    @property
    def damages_player(self) -> bool:
        return False

    def draw(self, ctx: RenderContext) -> None:
        target = ctx.rect(self.rect)
        radius = max(1, ctx.viewport.s(4))
        pygame.draw.rect(ctx.surface, AMMO_PICKUP_COLOR, target, border_radius=radius)
        inner = target.inflate(-target.width // 3, -target.height // 3)
        pygame.draw.rect(
            ctx.surface, AMMO_PICKUP_HIGHLIGHT_COLOR, inner, border_radius=max(1, radius // 2)
        )


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


def spawn_meteorite(rng: random.Random, area: tuple[int, int]) -> Meteorite:
    """`area` ist die Spawn-Fläche im Referenzraum (`REFERENCE_SIZE`), nicht das Fenster."""
    width, height = area
    variant = rng.choice(METEORITE_VARIANTS)
    diameter = variant.radius * 2
    image_name = rng.choice(variant.images)
    y = rng.randint(0, max(0, height - diameter))
    return Meteorite(
        pygame.Rect(width, y, diameter, diameter),
        METEORITE_SPEED,
        image_name,
        hp=variant.hp,
        contact_damage=variant.contact_damage,
    )


def spawn_wave_enemy(rng: random.Random, area: tuple[int, int]) -> WaveEnemy:
    width, height = area
    w, h = ENEMY_SIZE
    y = rng.randint(0, height - h)
    return WaveEnemy(pygame.Rect(width, y, w, h), WAVE_ENEMY_SPEED)


def spawn_hunter_enemy(rng: random.Random, area: tuple[int, int]) -> HunterEnemy:
    width, height = area
    w, h = ENEMY_SIZE
    y = rng.randint(0, height - h)
    return HunterEnemy(pygame.Rect(width, y, w, h), HUNTER_ENEMY_SPEED)


def spawn_ammo_pickup(rng: random.Random, area: tuple[int, int]) -> AmmoPickup:
    width, height = area
    w, h = AMMO_PICKUP_SIZE
    y = rng.randint(0, max(0, height - h))
    return AmmoPickup(pygame.Rect(width, y, w, h), AMMO_PICKUP_SPEED)
