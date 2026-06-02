import functools
import random

import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.config import (
    BACKGROUND_COLOR,
    HUNTER_ENEMY_WEIGHT,
    METEORITE_WEIGHT,
    PLAYER_SIZE,
    PLAYER_START_POSITION,
    SPAWN_INTERVAL_RANGE,
    WAVE_ENEMY_WEIGHT,
)
from meteorite_dash.context import GameContext
from meteorite_dash.entities import (
    Entity,
    collides_with_any,
    spawn_hunter_enemy,
    spawn_meteorite,
    spawn_wave_enemy,
)
from meteorite_dash.player import Player
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.spawner import SpawnEntry, Spawner


class GameScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.entities: list[Entity] = []
        self._build()

    def _scales(self) -> tuple[float, float, float]:
        vp = self.context.viewport
        return vp.scale_x, vp.scale_y, vp.scale

    def _scaled_player_size(self, su: float) -> tuple[int, int]:
        return (round(PLAYER_SIZE[0] * su), round(PLAYER_SIZE[1] * su))

    def _spawn_table(self, sx: float, sy: float, su: float) -> list[SpawnEntry]:
        return [
            SpawnEntry(METEORITE_WEIGHT, functools.partial(spawn_meteorite, sx=sx, su=su)),
            SpawnEntry(
                WAVE_ENEMY_WEIGHT,
                functools.partial(spawn_wave_enemy, sx=sx, sy=sy, su=su),
            ),
            SpawnEntry(
                HUNTER_ENEMY_WEIGHT,
                functools.partial(spawn_hunter_enemy, sx=sx, sy=sy, su=su),
            ),
        ]

    def _build(self) -> None:
        sx, sy, su = self._scales()
        size = self.context.screen.get_size()
        image = self.context.assets.load_ship(
            self.context.state.selected_ship_filename, self._scaled_player_size(su)
        )
        start = (round(PLAYER_START_POSITION[0] * sx), round(PLAYER_START_POSITION[1] * sy))
        self.player = Player(image, start)
        self.spawner = Spawner(
            self._spawn_table(sx, sy, su), size, random.Random(), SPAWN_INTERVAL_RANGE
        )

    def on_resize(self, size: tuple[int, int]) -> None:
        sx, sy, su = self._scales()
        image = self.context.assets.load_ship(
            self.context.state.selected_ship_filename, self._scaled_player_size(su)
        )
        centery = self.player.rect.centery
        self.player.image = image
        self.player.rect = image.get_rect()
        self.player.rect.x = round(PLAYER_START_POSITION[0] * sx)
        self.player.rect.centery = centery
        # Re-clamp into the (possibly smaller) window; Player.update only blocks
        # further out-of-bounds movement, it never pulls a stranded ship back in.
        self.player.rect.y = max(0, min(self.player.rect.y, size[1] - self.player.rect.height))
        self.spawner.screen_size = size
        self.spawner.set_table(self._spawn_table(sx, sy, su))

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == GAME_MUSIC_ENDED:
            self.context.music.advance_track()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.context.screen.get_height())
        self.context.starfield.update(dt)

        self.entities.extend(self.spawner.update(dt))
        player_y = self.player.rect.centery
        for entity in self.entities:
            entity.update(dt, player_y)
        self.entities = [entity for entity in self.entities if not entity.is_off_screen]

        if collides_with_any(self.player.rect, self.entities):
            self.finish(Transition.DEATH_SCREEN)

    def draw(self) -> None:
        self.context.screen.fill(BACKGROUND_COLOR)
        for entity in self.entities:
            entity.draw(self.context.screen)
        self.context.starfield.draw(self.context.screen)
        self.player.draw(self.context.screen)
        pygame.display.flip()
