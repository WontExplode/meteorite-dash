from typing import Protocol

import pygame

from meteorite_dash.config import DRAG, REFERENCE_SIZE
from meteorite_dash.ships import ShipSpec


class KeyStates(Protocol):
    def __getitem__(self, key: int) -> bool:
        pass


class Player:
    def __init__(self, image: pygame.Surface, position: tuple[int, int], spec: ShipSpec) -> None:
        self.image = image
        self.rect = image.get_rect(topleft=position)
        self.spec = spec
        self.velocity = 0.0  # px/s, vertikal; negativ = aufwärts
        self._y = float(position[1])  # Float-Position für verlustfreies Integrieren

    def update(self, dt: float, keys: KeyStates, max_height: int) -> None:
        direction = 0
        if keys[pygame.K_UP]:
            direction -= 1
        if keys[pygame.K_DOWN]:
            direction += 1

        # Schub skaliert mit der Fensterhöhe, damit die vertikale Durchquerungszeit
        # fenster-unabhängig bleibt; bei Referenzhöhe ist der Faktor exakt 1.0.
        thrust = self.spec.thrust * (max_height / REFERENCE_SIZE[1])
        # Linearer Widerstand: F = direction * thrust - DRAG * v, dann a = F / m.
        force = direction * thrust - DRAG * self.velocity
        self.velocity += force / self.spec.mass * dt
        self._y += self.velocity * dt

        bottom = max_height - self.rect.height
        if self._y < 0:
            self._y = 0.0
            self.velocity = 0.0
        elif self._y > bottom:
            self._y = float(bottom)
            self.velocity = 0.0

        self.rect.y = round(self._y)

    def set_vertical_position(self, y: float) -> None:
        """Setzt die vertikale Position von außen (z. B. nach Resize) und hält
        Float-Position und Rect synchron."""
        self._y = float(y)
        self.rect.y = round(self._y)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.image, self.rect)
