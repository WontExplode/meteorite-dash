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
        image = context.assets.load_ship(context.state.selected_ship_filename, PLAYER_SIZE)
        self.player = Player(image, PLAYER_START_POSITION)
        self.entities: list[Entity] = []
        table = [
            SpawnEntry(METEORITE_WEIGHT, spawn_meteorite),
            SpawnEntry(WAVE_ENEMY_WEIGHT, spawn_wave_enemy),
            SpawnEntry(HUNTER_ENEMY_WEIGHT, spawn_hunter_enemy),
        ]
        self.spawner = Spawner(
            table, context.screen.get_size(), random.Random(), SPAWN_INTERVAL_RANGE
        )

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

        self.entities.extend(self.spawner.update(dt))
        player_y = self.player.rect.centery
        for entity in self.entities:
            entity.update(dt, player_y)
        self.entities = [entity for entity in self.entities if not entity.is_off_screen]

        if collides_with_any(self.player.rect, self.entities):
            self.finish(Transition.MAIN_MENU)

    def draw(self) -> None:
        self.context.screen.fill(BACKGROUND_COLOR)
        for entity in self.entities:
            entity.draw(self.context.screen)
        self.player.draw(self.context.screen)
        pygame.display.flip()
