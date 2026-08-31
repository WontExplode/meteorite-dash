"""Spielerschiff: vertikale Bewegung mit Trägheit im Referenzraum."""

import pygame

from meteorite_dash.config import DRAG, PLAYER_SIZE, REFERENCE_SIZE
from meteorite_dash.hitbox import ship_mask
from meteorite_dash.inputs import InputFrame
from meteorite_dash.ships import ShipSpec


class Player:
    """Spielerschiff — reine Logik im Referenzraum, hält keine Surface.

    Gezeichnet wird es von der Szene über den `RenderContext`; so bleibt die
    Bewegung fenster-unabhängig und ohne Display testbar. `mask` ist die
    Silhouette des Schiffssprites — die Box ist deutlich größer als das Schiff,
    Kollision läuft deshalb pixelgenau (`hitbox.py`).
    """

    def __init__(
        self,
        position: tuple[int, int],
        spec: ShipSpec,
        *,
        extra_hp: int = 0,
    ) -> None:
        if extra_hp < 0:
            raise ValueError("extra_hp darf nicht negativ sein")
        self.rect = pygame.Rect(position, PLAYER_SIZE)
        self.spec = spec
        # Zubehör "Panzerung" legt Hüllenpunkte auf den Schiffswert drauf.
        self.max_hp = spec.hp + extra_hp
        self.hp = self.max_hp
        self.velocity = 0.0  # px/s, vertikal; negativ = aufwärts
        self._y = float(position[1])  # Float-Position für verlustfreies Integrieren

    @property
    def mask(self) -> pygame.mask.Mask:
        """Alphamaske des Schiffssprites in `PLAYER_SIZE` (gecacht in `hitbox.py`)."""
        return ship_mask(self.spec.sprite, PLAYER_SIZE)

    def update(self, dt: float, inputs: InputFrame) -> None:
        """Integriert einen Tick: Schub aus `UP`/`DOWN`, linearer Widerstand, Rand-Clamp.

        `dt` kommt aus `Simulation.step` (`SIM_DT`); am oberen und unteren Rand
        wird die Geschwindigkeit genullt.
        """
        direction = 0
        if InputFrame.UP in inputs:
            direction -= 1
        if InputFrame.DOWN in inputs:
            direction += 1

        # Linearer Widerstand: F = direction * thrust - DRAG * v, dann a = F / m.
        force = direction * self.spec.thrust - DRAG * self.velocity
        self.velocity += force / self.spec.mass * dt
        self._y += self.velocity * dt

        bottom = REFERENCE_SIZE[1] - self.rect.height
        if self._y < 0:
            self._y = 0.0
            self.velocity = 0.0
        elif self._y > bottom:
            self._y = float(bottom)
            self.velocity = 0.0

        self.rect.y = round(self._y)

    def set_vertical_position(self, y: float) -> None:
        """Setzt die vertikale Position von außen und hält Float-Position und
        Rect synchron."""
        self._y = float(y)
        self.rect.y = round(self._y)

    def state_key(self) -> tuple[object, ...]:
        """Kanonischer Zustand für den Simulations-Hash (Floats als Hex, verlustfrei)."""
        return (tuple(self.rect), self._y.hex(), self.velocity.hex(), self.hp, self.max_hp)
