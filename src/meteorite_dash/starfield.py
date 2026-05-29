from dataclasses import dataclass
from random import Random

import pygame


@dataclass
class Star:
    x: float
    y: float
    speed: float
    radius: int
    color: tuple[int, int, int]


class StarField:
    def __init__(self, width: int, height: int, star_count: int = 120) -> None:
        self.width = width
        self.height = height
        self.random = Random()
        self.stars = [self._create_star(start_anywhere=True) for _ in range(star_count)]

    def update(self, dt: float) -> None:
        for star in self.stars:
            star.x -= star.speed * dt

            if star.x < -star.radius:
                self._reset_star(star)

    def draw(self, screen: pygame.Surface) -> None:
        for star in self.stars:
            pygame.draw.circle(
                screen,
                star.color,
                (round(star.x), round(star.y)),
                star.radius,
            )

    def _create_star(self, start_anywhere: bool) -> Star:
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
        new_star = self._create_star(start_anywhere=False)
        star.x = new_star.x
        star.y = new_star.y
        star.speed = new_star.speed
        star.radius = new_star.radius
        star.color = new_star.color
