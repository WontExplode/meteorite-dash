from typing import Protocol

import pygame

from meteorite_dash.config import PLAYER_SPEED, REFERENCE_SIZE


class KeyStates(Protocol):
    def __getitem__(self, key: int) -> bool:
        pass


class Player:
    def __init__(self, image: pygame.Surface, position: tuple[int, int]) -> None:
        self.image = image
        self.rect = image.get_rect(topleft=position)

    def update(self, dt: float, keys: KeyStates, max_height: int) -> None:
        # Speed scales with the window height so vertical traversal time stays
        # constant; at the reference height this is exactly PLAYER_SPEED.
        speed = PLAYER_SPEED * (max_height / REFERENCE_SIZE[1])
        movement = int(speed * dt)

        if keys[pygame.K_UP] and self.rect.y > 0:
            self.rect.y -= movement
        if keys[pygame.K_DOWN] and self.rect.y < max_height - self.rect.height:
            self.rect.y += movement

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.image, self.rect)
