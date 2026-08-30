"""Scrollendes Sternenfeld als Hintergrund-Deko.

Reines Rendering: rechnet in Fensterpixeln, nutzt ungeseedeten Zufall und
Wandzeit. Gehört nicht zur Simulation und beeinflusst keine Replays.
"""

from dataclasses import dataclass
from random import Random

import pygame


@dataclass
class Star:
    """Ein Hintergrundstern in Fensterpixeln; Helligkeit als Grauwert."""

    x: float
    y: float
    speed: float
    radius: int
    color: tuple[int, int, int]


class StarField:
    """Parallax-Sternenfeld, das nach links scrollt und Sterne rechts neu setzt."""

    def __init__(self, width: int, height: int, star_count: int = 120) -> None:
        self.width = width
        self.height = height
        self.random = Random()
        self.stars = [self._create_star(start_anywhere=True) for _ in range(star_count)]

    def update(self, dt: float) -> None:
        """Bewegt alle Sterne nach links; links hinausgelaufene starten rechts neu."""
        for star in self.stars:
            star.x -= star.speed * dt

            if star.x < -star.radius:
                self._reset_star(star)

    def resize(self, width: int, height: int) -> None:
        """Skaliert die Sternpositionen proportional auf die neue Fenstergröße."""
        scale_x = width / self.width if self.width else 1.0
        scale_y = height / self.height if self.height else 1.0
        self.width = width
        self.height = height
        for star in self.stars:
            star.x *= scale_x
            star.y *= scale_y

    def draw(self, screen: pygame.Surface) -> None:
        """Zeichnet jeden Stern als gefüllten Kreis direkt in Fensterpixeln."""
        for star in self.stars:
            pygame.draw.circle(
                screen,
                star.color,
                (round(star.x), round(star.y)),
                star.radius,
            )

    def _create_star(self, start_anywhere: bool) -> Star:
        """Würfelt einen Stern; `start_anywhere` verteilt ihn im Bild statt am rechten Rand."""
        radius = self.random.choice((1, 1, 1, 2))
        brightness = self.random.randint(150, 255)
        return Star(
            x=self.random.uniform(0, self.width) if start_anywhere else self.width + radius,
            y=self.random.uniform(0, self.height),
            speed=self.random.uniform(30, 160),
            radius=radius,
            color=(brightness, brightness, brightness),
        )

    def _reset_star(self, star: Star) -> None:
        """Setzt einen Stern in-place auf frische Werte am rechten Rand."""
        new_star = self._create_star(start_anywhere=False)
        star.x = new_star.x
        star.y = new_star.y
        star.speed = new_star.speed
        star.radius = new_star.radius
        star.color = new_star.color
