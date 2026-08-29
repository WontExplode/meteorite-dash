from typing import Protocol

import pygame

from meteorite_dash.config import DRAG, PLAYER_SIZE, REFERENCE_SIZE
from meteorite_dash.ships import ShipSpec


class KeyStates(Protocol):
    def __getitem__(self, key: int) -> bool:
        pass


class Player:
    """Spielerschiff — reine Logik im Referenzraum, hält keine Surface.

    Gezeichnet wird es von der Szene über den `RenderContext`; so bleibt die
    Bewegung fenster-unabhängig und ohne Display testbar.
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

    def update(self, dt: float, keys: KeyStates) -> None:
        direction = 0
        if keys[pygame.K_UP]:
            direction -= 1
        if keys[pygame.K_DOWN]:
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
