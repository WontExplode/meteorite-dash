"""Gegner, Hindernisse und Pickups: `Entity`-Basis, Varianten und Spawn-Fabriken.

Alles hier rechnet im Referenzraum (`REFERENCE_SIZE`) und hält keine Surfaces;
gezeichnet wird über den `RenderContext`. Die `spawn_*`-Fabriken nehmen einen
injizierten `random.Random` und sind damit deterministisch testbar.
"""

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
from meteorite_dash.hitbox import (
    HasHitbox,
    circle_mask,
    image_mask,
    left_triangle_mask,
    overlaps,
    solid_mask,
)
from meteorite_dash.mathutil import det_sin
from meteorite_dash.render import RenderContext


class Entity(ABC):
    """Basis für alles, was von rechts nach links fliegt. `rect` ist die Hitbox.

    Alle Koordinaten liegen im Referenzraum (`REFERENCE_SIZE`); erst `draw`
    übersetzt über den `RenderContext` ins Fenster. `mask` verfeinert `rect`
    zur pixelgenauen Silhouette (`hitbox.py`); Subklassen liefern die Form,
    die sie auch zeichnen.
    """

    def __init__(self, rect: pygame.Rect, speed_x: float) -> None:
        self.rect = rect
        self._x = float(rect.x)
        self._y = float(rect.y)
        self.speed_x = speed_x

    @property
    def damages_player(self) -> bool:
        """Ob Berührung dem Spieler schadet; Pickups überschreiben mit False."""
        return True

    @property
    def mask(self) -> pygame.mask.Mask:
        """Pixelgenaue Silhouette in `rect`-Größe; Standard ist die volle Fläche."""
        return solid_mask(self.rect.size)

    @property
    def is_off_screen(self) -> bool:
        """True, sobald die Hitbox links aus dem Referenzraum geflogen ist."""
        return self.rect.right < 0

    def update(self, dt: float, player_y: int, speed_scale: float = 1.0) -> None:
        """`speed_scale` kommt vom Schwierigkeits-Director (`DifficultyParams`)."""
        self._x -= self.speed_x * speed_scale * dt
        self._update_vertical(dt, player_y)
        self.rect.x = round(self._x)
        self.rect.y = round(self._y)

    def state_key(self) -> tuple[object, ...]:
        """Kanonischer Zustand für den Simulations-Hash (Floats als Hex, verlustfrei)."""
        return (
            type(self).__name__,
            tuple(self.rect),
            self._x.hex(),
            self._y.hex(),
            self.speed_x.hex(),
        )

    def _update_vertical(self, dt: float, player_y: int) -> None:  # noqa: B027  (optional hook)
        """Standard: keine vertikale Bewegung; Subklassen überschreiben dies."""

    @abstractmethod
    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet die Entity über den `RenderContext` ins Fenster."""
        raise NotImplementedError


class DamageableEntity(Entity):
    """Entity mit Trefferpunkten und Kollisionsschaden.

    Projektile ziehen über `take_damage` HP ab; bei Berührung kostet sie den
    Spieler `contact_damage` (siehe `combat.py`).
    """

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
        """Zieht `amount` HP ab; True, wenn die Entity damit zerstört ist."""
        self.hp -= amount
        return self.hp <= 0

    def state_key(self) -> tuple[object, ...]:
        """Ergänzt den Basiszustand um HP und Kollisionsschaden."""
        return (*super().state_key(), self.hp, self.contact_damage)


class Meteorite(DamageableEntity):
    """Meteorit in einer Größe aus `METEORITE_VARIANTS`, fliegt geradeaus.

    Merkt sich nur den Bild-Dateinamen; ohne Bild wird ein Kreis gezeichnet.
    """

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

    def state_key(self) -> tuple[object, ...]:
        """Ergänzt den Zustand um die Bildvariante."""
        return (*super().state_key(), self.image_name)

    @property
    def mask(self) -> pygame.mask.Mask:
        """Alphamaske des Sprites; ohne Bild der eingeschriebene Kreis (wie gezeichnet)."""
        if self.image_name is None:
            return circle_mask(self.rect.size)
        return image_mask(self.image_name, self.rect.size)

    def draw(self, ctx: RenderContext) -> None:
        """Blittet das Sprite in Fenstergröße; Fallback: Kreis in `METEORITE_COLOR`."""
        target = ctx.rect(self.rect)
        image = ctx.image(self.image_name, target.size) if self.image_name else None
        if image is not None:
            ctx.surface.blit(image, target)
            return

        radius = max(1, target.width // 2)
        pygame.draw.circle(ctx.surface, METEORITE_COLOR, target.center, radius)


class WaveEnemy(DamageableEntity):
    """Gegner auf Sinus-Bahn um seine Start-Höhe (`amplitude`, `frequency`)."""

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
        """Sinus über die verstrichene Zeit; `det_sin` hält die Bahn plattformstabil."""
        self._elapsed += dt
        self._y = self._base_y + self._amplitude * det_sin(
            2 * math.pi * self._frequency * self._elapsed
        )

    def state_key(self) -> tuple[object, ...]:
        """Ergänzt den Zustand um die verstrichene Zeit (Phase der Bahn)."""
        return (*super().state_key(), self._elapsed.hex())

    @property
    def mask(self) -> pygame.mask.Mask:
        """Dreieck-Silhouette, deckungsgleich mit `draw`."""
        return left_triangle_mask(self.rect.size)

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet ein nach links zeigendes Dreieck in `WAVE_ENEMY_COLOR`."""
        _draw_left_triangle(ctx.surface, ctx.rect(self.rect), WAVE_ENEMY_COLOR)


class HunterEnemy(DamageableEntity):
    """Gegner, der den Spieler vertikal mit `vertical_speed` verfolgt."""

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
        """Nähert sich der Spieler-Höhe mit fester Geschwindigkeit, ohne zu überschießen."""
        target = player_y - self.rect.height / 2  # Ziel-top, damit Center auf player_y zielt
        step = self._vertical_speed * dt
        if abs(target - self._y) <= step:
            self._y = target
        elif target > self._y:
            self._y += step
        else:
            self._y -= step

    @property
    def mask(self) -> pygame.mask.Mask:
        """Dreieck-Silhouette, deckungsgleich mit `draw`."""
        return left_triangle_mask(self.rect.size)

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet ein nach links zeigendes Dreieck in `HUNTER_ENEMY_COLOR`."""
        _draw_left_triangle(ctx.surface, ctx.rect(self.rect), HUNTER_ENEMY_COLOR)


class AmmoPickup(Entity):
    """Harmloses Munitions-Pickup; Aufsammeln füllt die Standardwaffe (`Simulation`)."""

    @property
    def damages_player(self) -> bool:
        """Pickups schaden nie."""
        return False

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet ein abgerundetes Rechteck mit hellem Kern."""
        target = ctx.rect(self.rect)
        radius = max(1, ctx.viewport.s(4))
        pygame.draw.rect(ctx.surface, AMMO_PICKUP_COLOR, target, border_radius=radius)
        inner = target.inflate(-target.width // 3, -target.height // 3)
        pygame.draw.rect(
            ctx.surface, AMMO_PICKUP_HIGHLIGHT_COLOR, inner, border_radius=max(1, radius // 2)
        )


def _draw_left_triangle(surface: pygame.Surface, rect: pygame.Rect, color: Color) -> None:
    """Dreieck mit Spitze am linken Rand des Rechtecks (Gegner-Silhouette)."""
    points = [(rect.left, rect.centery), (rect.right, rect.top), (rect.right, rect.bottom)]
    pygame.draw.polygon(surface, color, points)


def collides_with_any(player: HasHitbox, entities: Iterable[Entity]) -> bool:
    """True, wenn der Spieler eine schädliche Entity pixelgenau berührt."""
    return any(entity.damages_player and overlaps(player, entity) for entity in entities)


def collect_pickups(player: HasHitbox, entities: list[Entity]) -> list[Entity]:
    """Entfernt eingesammelte Munitions-Pickups und gibt sie zurück."""
    collected: list[Entity] = []
    remaining: list[Entity] = []
    for entity in entities:
        if isinstance(entity, AmmoPickup) and overlaps(player, entity):
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
    """Wellen-Gegner am rechten Rand auf zufälliger Höhe; `area` ist der Referenzraum."""
    width, height = area
    w, h = ENEMY_SIZE
    y = rng.randint(0, height - h)
    return WaveEnemy(pygame.Rect(width, y, w, h), WAVE_ENEMY_SPEED)


def spawn_hunter_enemy(rng: random.Random, area: tuple[int, int]) -> HunterEnemy:
    """Jäger am rechten Rand auf zufälliger Höhe; `area` ist der Referenzraum."""
    width, height = area
    w, h = ENEMY_SIZE
    y = rng.randint(0, height - h)
    return HunterEnemy(pygame.Rect(width, y, w, h), HUNTER_ENEMY_SPEED)


def spawn_ammo_pickup(rng: random.Random, area: tuple[int, int]) -> AmmoPickup:
    """Munitions-Pickup am rechten Rand auf zufälliger Höhe; `area` ist der Referenzraum."""
    width, height = area
    w, h = AMMO_PICKUP_SIZE
    y = rng.randint(0, max(0, height - h))
    return AmmoPickup(pygame.Rect(width, y, w, h), AMMO_PICKUP_SPEED)
