"""Münzen als Collectible (Issue #14): Muster-Layouts, Spawn-Fabrik und Formationen.

Ein Muster ist eine reine Funktion `Random -> Offsets` im 800x600-Referenzraum.
`spawn_coin_formation` setzt die Offsets an einen passenden Anker und liefert
eine `CoinFormation`, die ihre Münzen als Einheit bewegt, einsammelt und bei
Komplettierung einmalig den Bonus auszahlt. Wie alle Entities leben Münzen im
Referenzraum; erst `draw` skaliert über den `RenderContext` ins Fenster.
"""

import math
import random
from collections.abc import Callable, Iterable, Sequence
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
from meteorite_dash.hitbox import HasHitbox, circle_mask, overlaps
from meteorite_dash.mathutil import det_hypot, det_sin
from meteorite_dash.render import RenderContext

Offset = tuple[float, float]
LayoutFn = Callable[[random.Random], list[Offset]]


class Pickup(NamedTuple):
    """Ergebnis eines Einsammel-Schritts: Münzwert plus ggf. Formations-Bonus."""

    coins: int
    bonus: int

    @property
    def total(self) -> int:
        """Münzwert plus Bonus."""
        return self.coins + self.bonus


class Coin(Entity):
    """Einzelne Münze: harmlose `Entity`, prozedural gezeichnet, ohne Bild-Asset.

    `spin_phase` versetzt die Dreh-Animation, damit Münzen eines Musters nicht
    synchron blinken. Die Animationszeit liegt im `state_key`.
    """

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
        """Münzen schaden nie; Berührung sammelt ein."""
        return False

    @property
    def mask(self) -> pygame.mask.Mask:
        """Volle Scheibe — die Dreh-Animation schmälert nur das Bild, nie die Hitbox."""
        return circle_mask(self.rect.size)

    def update(self, dt: float, player_y: int, speed_scale: float = 1.0) -> None:
        """Bewegt wie `Entity` und zählt die Zeit für die Dreh-Animation hoch."""
        super().update(dt, player_y, speed_scale)
        self._elapsed += dt

    def state_key(self) -> tuple[object, ...]:
        """Ergänzt den Basiszustand um Wert und Animationszeit."""
        return (*super().state_key(), self.value, self._elapsed.hex())

    def pull_toward(self, target: tuple[int, int], step: float) -> None:
        """Zieht die Münze um höchstens `step` px auf `target` zu (Magnet-Zubehör)."""
        dx = target[0] - self.rect.centerx
        dy = target[1] - self.rect.centery
        distance = det_hypot(dx, dy)
        if distance == 0:
            return
        factor = min(1.0, step / distance)
        self._x += dx * factor
        self._y += dy * factor
        self.rect.x = round(self._x)
        self.rect.y = round(self._y)

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet die Münze als rotierende Gold-Scheibe (Ellipse mit Rand)."""
        # Dreh-Animation: Ellipsenbreite folgt |cos|, Höhe bleibt konstant. Die
        # Mindestbreite hält die Kante sichtbar, statt zum Strich zu werden.
        target = ctx.rect(self.rect)
        angle = 2 * math.pi * COIN_SPIN_HZ * self._elapsed + self._spin_phase
        spin = COIN_MIN_SPIN_WIDTH + (1 - COIN_MIN_SPIN_WIDTH) * abs(math.cos(angle))
        width = max(2, round(target.width * spin))
        disc = pygame.Rect(0, 0, width, target.height)
        disc.center = target.center
        pygame.draw.ellipse(ctx.surface, COIN_COLOR, disc)
        pygame.draw.ellipse(ctx.surface, COIN_RIM_COLOR, disc, max(1, target.height // 8))


# --- Muster-Layouts (Referenzraum, Offsets relativ zum Anker) -----------------


def _line(rng: random.Random) -> list[Offset]:
    """Gerade Reihe aus 6 bis 10 Münzen."""
    count = rng.randint(6, 10)
    return [(i * COIN_SPACING, 0.0) for i in range(count)]


def _wave(rng: random.Random) -> list[Offset]:
    """Volle Sinuswelle über 8 bis 12 Münzen."""
    count = rng.randint(8, 12)
    return [
        (i * COIN_SPACING, COIN_WAVE_AMPLITUDE * det_sin(2 * math.pi * i / (count - 1)))
        for i in range(count)
    ]


def _arc(rng: random.Random) -> list[Offset]:
    """Halbbogen aus 6 bis 9 Münzen, zufällig nach oben oder unten gewölbt."""
    count = rng.randint(6, 9)
    direction = rng.choice((-1.0, 1.0))
    return [
        (i * COIN_SPACING, direction * COIN_ARC_HEIGHT * det_sin(math.pi * i / (count - 1)))
        for i in range(count)
    ]


def _zigzag(rng: random.Random) -> list[Offset]:
    """Zwei Zacken mit 2 bis 3 Stufen je Flanke, Richtung zufällig."""
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
    """Raute aus fünf Spalten (1-2-3-2-1 Münzen), ohne Zufall."""
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
    """Layout-Funktion zum Muster-Namen; `ValueError` bei unbekanntem Namen."""
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
        """True, sobald keine Münze mehr übrig ist (eingesammelt oder verpasst)."""
        return not self.coins

    def update(self, dt: float, player_y: int, speed_scale: float = 1.0) -> None:
        """Bewegt alle Münzen; links hinausgeflogene zählen als verpasst."""
        remaining: list[Coin] = []
        for coin in self.coins:
            coin.update(dt, player_y, speed_scale)
            if coin.is_off_screen:
                self.missed += 1
            else:
                remaining.append(coin)
        self.coins = remaining

    def attract(self, target: tuple[int, int], radius: float, step: float) -> None:
        """Zieht alle Münzen im Umkreis `radius` um `target` um `step` px heran."""
        for coin in self.coins:
            if det_hypot(target[0] - coin.rect.centerx, target[1] - coin.rect.centery) <= radius:
                coin.pull_toward(target, step)

    def collect(self, player: HasHitbox) -> Pickup:
        """Sammelt Münzen ein, die der Spieler pixelgenau berührt.

        Der Bonus fällt genau einmal: beim letzten Einsammeln, wenn keine Münze
        verpasst wurde.
        """
        value = 0
        remaining: list[Coin] = []
        for coin in self.coins:
            if overlaps(player, coin):
                self.collected += 1
                value += coin.value
            else:
                remaining.append(coin)
        self.coins = remaining
        completed = value > 0 and not self.coins and self.missed == 0
        return Pickup(value, self.bonus if completed else 0)

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet alle verbliebenen Münzen."""
        for coin in self.coins:
            coin.draw(ctx)

    def state_key(self) -> tuple[object, ...]:
        """Kanonischer Zustand: Münzen, Bonus und Zähler."""
        return (
            tuple(coin.state_key() for coin in self.coins),
            self.bonus,
            self.collected,
            self.missed,
        )


def coin_rects(formations: Iterable[CoinFormation]) -> list[pygame.Rect]:
    """Hitboxen aller Münzen der Formationen (Spawn-Ausschluss gegen Gefahren)."""
    return [coin.rect for formation in formations for coin in formation.coins]


def is_clear(
    rects: Iterable[pygame.Rect],
    obstacles: Sequence[pygame.Rect],
    clearance: int,
) -> bool:
    """True, wenn keines der `rects` — um `clearance` aufgeblasen — ein Hindernis berührt.

    Spawn-Prüfung in beide Richtungen: Gefahr gegen laufende Münz-Muster und
    neues Münz-Muster gegen Gefahren am rechten Rand.
    """
    grow = 2 * clearance
    return all(rect.inflate(grow, grow).collidelist(obstacles) == -1 for rect in rects)


def spawn_coin_formation(
    rng: random.Random,
    area: tuple[int, int],
    *,
    pattern: CoinPatternSpec,
) -> CoinFormation:
    """`area` ist die Spawn-Fläche im Referenzraum (`REFERENCE_SIZE`)."""
    width, height = area
    offsets = layout_for(pattern.name)(rng)
    diameter = COIN_RADIUS * 2
    dxs = [round(dx) for dx, _ in offsets]
    dys = [round(dy) for _, dy in offsets]

    # Anker so wählen, dass das ganze Muster vertikal ins Fenster passt.
    low = -min(dys)
    high = max(low, height - diameter - max(dys))
    anchor_y = rng.randint(low, high)

    coins = [
        Coin(
            pygame.Rect(width + dx, anchor_y + dy, diameter, diameter),
            COIN_SPEED,
            spin_phase=index * COIN_SPIN_PHASE_STEP,
        )
        for index, (dx, dy) in enumerate(zip(dxs, dys, strict=True))
    ]
    return CoinFormation(coins, pattern.bonus)
