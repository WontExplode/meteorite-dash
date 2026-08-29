"""Münzen als Collectible (Issue #14): Muster-Layouts, Spawn-Fabrik und Formationen.

Ein Muster ist eine reine Funktion `Random -> Offsets` im 800x600-Referenzraum.
`spawn_coin_formation` skaliert die Offsets auf das Fenster und liefert eine
`CoinFormation`, die ihre Münzen als Einheit bewegt, einsammelt und bei
Komplettierung einmalig den Bonus auszahlt.
"""

import math
import random
from collections.abc import Callable
from typing import NamedTuple

import pygame

from meteorite_dash.config import (
    COIN_ARC_HEIGHT,
    COIN_COLOR,
    COIN_MIN_SPIN_WIDTH,
    COIN_RADIUS,
    COIN_RIM_COLOR,
    COIN_ROW_SPACING,
    COIN_SPACING,
    COIN_SPEED,
    COIN_SPIN_HZ,
    COIN_SPIN_PHASE_STEP,
    COIN_VALUE,
    COIN_WAVE_AMPLITUDE,
    COIN_ZIGZAG_STEP,
    CoinPatternSpec,
)
from meteorite_dash.entities import Entity

Offset = tuple[float, float]
LayoutFn = Callable[[random.Random], list[Offset]]


class Pickup(NamedTuple):
    """Ergebnis eines Einsammel-Schritts: Münzwert plus ggf. Formations-Bonus."""

    coins: int
    bonus: int

    @property
    def total(self) -> int:
        return self.coins + self.bonus


class Coin(Entity):
    def __init__(
        self,
        rect: pygame.Rect,
        speed_x: float,
        *,
        value: int = COIN_VALUE,
        spin_phase: float = 0.0,
    ) -> None:
        super().__init__(rect, speed_x)
        self.value = value
        self._spin_phase = spin_phase
        self._elapsed = 0.0

    @property
    def damages_player(self) -> bool:
        return False

    def update(self, dt: float, player_y: int) -> None:
        super().update(dt, player_y)
        self._elapsed += dt

    def draw(self, surface: pygame.Surface) -> None:
        # Dreh-Animation: Ellipsenbreite folgt |cos|, Höhe bleibt konstant. Die
        # Mindestbreite hält die Kante sichtbar, statt zum Strich zu werden.
        angle = 2 * math.pi * COIN_SPIN_HZ * self._elapsed + self._spin_phase
        spin = COIN_MIN_SPIN_WIDTH + (1 - COIN_MIN_SPIN_WIDTH) * abs(math.cos(angle))
        width = max(2, round(self.rect.width * spin))
        disc = pygame.Rect(0, 0, width, self.rect.height)
        disc.center = self.rect.center
        pygame.draw.ellipse(surface, COIN_COLOR, disc)
        pygame.draw.ellipse(surface, COIN_RIM_COLOR, disc, max(1, self.rect.height // 8))


# --- Muster-Layouts (Referenzraum, Offsets relativ zum Anker) -----------------


def _line(rng: random.Random) -> list[Offset]:
    count = rng.randint(6, 10)
    return [(i * COIN_SPACING, 0.0) for i in range(count)]


def _wave(rng: random.Random) -> list[Offset]:
    count = rng.randint(8, 12)
    return [
        (i * COIN_SPACING, COIN_WAVE_AMPLITUDE * math.sin(2 * math.pi * i / (count - 1)))
        for i in range(count)
    ]


def _arc(rng: random.Random) -> list[Offset]:
    count = rng.randint(6, 9)
    direction = rng.choice((-1.0, 1.0))
    return [
        (i * COIN_SPACING, direction * COIN_ARC_HEIGHT * math.sin(math.pi * i / (count - 1)))
        for i in range(count)
    ]


def _zigzag(rng: random.Random) -> list[Offset]:
    # Zwei Zacken: `steps` Münzen hoch, `steps` runter, wiederholt.
    steps = rng.randint(2, 3)
    direction = rng.choice((-1.0, 1.0))
    offsets: list[Offset] = []
    for i in range(4 * steps + 1):
        phase = i % (2 * steps)
        level = phase if phase <= steps else 2 * steps - phase
        offsets.append((i * COIN_SPACING, direction * level * COIN_ZIGZAG_STEP))
    return offsets


def _diamond(rng: random.Random) -> list[Offset]:
    columns = (1, 2, 3, 2, 1)
    offsets: list[Offset] = []
    for col, rows in enumerate(columns):
        for row in range(rows):
            offsets.append((col * COIN_SPACING, (row - (rows - 1) / 2) * COIN_ROW_SPACING))
    return offsets


LAYOUTS: dict[str, LayoutFn] = {
    "line": _line,
    "wave": _wave,
    "arc": _arc,
    "zigzag": _zigzag,
    "diamond": _diamond,
}


def layout_for(name: str) -> LayoutFn:
    try:
        return LAYOUTS[name]
    except KeyError:
        raise ValueError(f"Unbekanntes Münz-Muster: {name!r}") from None


# --- Formation ------------------------------------------------------------------


class CoinFormation:
    """Ein gespawntes Münz-Muster als Einheit.

    Bewegt und zeichnet seine Münzen, zählt eingesammelte und verpasste. Sind
    alle Münzen eingesammelt und keine verpasst, zahlt `collect` einmalig den
    Bonus aus.
    """

    def __init__(self, coins: list[Coin], bonus: int) -> None:
        self.coins = coins
        self.bonus = bonus
        self.collected = 0
        self.missed = 0

    @property
    def is_finished(self) -> bool:
        return not self.coins

    def update(self, dt: float, player_y: int) -> None:
        remaining: list[Coin] = []
        for coin in self.coins:
            coin.update(dt, player_y)
            if coin.is_off_screen:
                self.missed += 1
            else:
                remaining.append(coin)
        self.coins = remaining

    def collect(self, player_rect: pygame.Rect) -> Pickup:
        value = 0
        remaining: list[Coin] = []
        for coin in self.coins:
            if player_rect.colliderect(coin.rect):
                self.collected += 1
                value += coin.value
            else:
                remaining.append(coin)
        self.coins = remaining
        completed = value > 0 and not self.coins and self.missed == 0
        return Pickup(value, self.bonus if completed else 0)

    def draw(self, surface: pygame.Surface) -> None:
        for coin in self.coins:
            coin.draw(surface)


def spawn_coin_formation(
    rng: random.Random,
    screen_size: tuple[int, int],
    *,
    pattern: CoinPatternSpec,
    sx: float = 1.0,
    sy: float = 1.0,
    su: float = 1.0,
) -> CoinFormation:
    width, height = screen_size
    offsets = layout_for(pattern.name)(rng)
    diameter = max(1, round(COIN_RADIUS * 2 * su))
    dxs = [round(dx * sx) for dx, _ in offsets]
    dys = [round(dy * sy) for _, dy in offsets]

    # Anker so wählen, dass das ganze Muster vertikal ins Fenster passt.
    low = -min(dys)
    high = max(low, height - diameter - max(dys))
    anchor_y = rng.randint(low, high)

    coins = [
        Coin(
            pygame.Rect(width + dx, anchor_y + dy, diameter, diameter),
            COIN_SPEED * sx,
            spin_phase=index * COIN_SPIN_PHASE_STEP,
        )
        for index, (dx, dy) in enumerate(zip(dxs, dys, strict=True))
    ]
    return CoinFormation(coins, pattern.bonus)
