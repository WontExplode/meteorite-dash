from typing import Literal

import pygame

from meteorite_dash.assets import image_path

GameResult = Literal["menu", "quit"]


class Game:
    def __init__(
        self, screen: pygame.Surface, clock: pygame.time.Clock, ship_filename: str
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.player_image = pygame.image.load(image_path(ship_filename)).convert_alpha()
        self.player_image = pygame.transform.scale(self.player_image, (64, 64))
        self.player_image = pygame.transform.rotate(self.player_image, -90)
        self.player = self.player_image.get_rect(topleft=(50, 100))

    def run(self) -> GameResult:
        while True:
            dt = self.clock.tick(60) / 1000

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "menu"

            self._update_player(dt)
            self._draw()

    def _update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        speed = 300
        movement = int(speed * dt)

        if keys[pygame.K_UP] and self.player.y > 0:
            self.player.y -= movement
        if keys[pygame.K_DOWN] and self.player.y < self.screen.get_height() - self.player.height:
            self.player.y += movement

    def _draw(self) -> None:
        self.screen.fill((10, 10, 20))
        self.screen.blit(self.player_image, self.player)
        pygame.display.flip()
