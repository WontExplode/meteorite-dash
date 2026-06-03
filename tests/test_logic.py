import random

import pygame
import pytest

from meteorite_dash.assets import SHIP_IMAGES
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import GAME_MUSIC_TRACKS, MENU_ITEMS
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.entities import (
    HunterEnemy,
    Meteorite,
    WaveEnemy,
    collides_with_any,
)
from meteorite_dash.player import Player
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.scenes.ship_selection import ShipSelection
from meteorite_dash.score import DistanceScore, format_light_years
from meteorite_dash.spawner import SpawnEntry, Spawner


class FakeKeys:
    def __init__(self, pressed: set[int]) -> None:
        self._pressed = pressed

    def __getitem__(self, key: int) -> bool:
        return key in self._pressed


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def test_main_menu_navigation_wraps(context: GameContext) -> None:
    menu = MainMenu(context)
    assert menu.selected_index == 0

    menu.handle_event(_keydown(pygame.K_UP))
    assert menu.selected_index == len(MENU_ITEMS) - 1

    menu.handle_event(_keydown(pygame.K_DOWN))
    assert menu.selected_index == 0


def test_main_menu_actions_map_to_transitions(context: GameContext) -> None:
    menu = MainMenu(context)
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.START_GAME


def test_ship_selection_navigation_wraps(context: GameContext) -> None:
    selection = ShipSelection(context)
    assert context.state.selected_ship_index == 0

    selection.handle_event(_keydown(pygame.K_LEFT))
    assert context.state.selected_ship_index == len(SHIP_IMAGES) - 1

    selection.handle_event(_keydown(pygame.K_RIGHT))
    assert context.state.selected_ship_index == 0


def test_ship_selection_confirm_returns_to_menu(context: GameContext) -> None:
    selection = ShipSelection(context)
    selection.handle_event(_keydown(pygame.K_ESCAPE))
    assert selection._transition is Transition.MAIN_MENU


def test_music_player_track_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    player = MusicPlayer()
    monkeypatch.setattr(player, "_load_and_play", lambda filename: None)

    indices = []
    for _ in range(len(GAME_MUSIC_TRACKS) + 1):
        player.advance_track()
        indices.append(player.track_index)

    expected = [(i + 1) % len(GAME_MUSIC_TRACKS) for i in range(len(GAME_MUSIC_TRACKS) + 1)]
    assert indices == expected


def test_game_state_selected_ship_filename() -> None:
    state = GameState(selected_ship_index=1)
    assert state.selected_ship_filename == SHIP_IMAGES[1]


def test_distance_score_tracks_light_years() -> None:
    score = DistanceScore(light_years_per_second=12.0)
    score.update(2.5)
    assert score.light_years == 30.0
    assert score.formatted() == "000030"


def test_format_light_years() -> None:
    assert format_light_years(123.9) == "000123"


def test_distance_score_uses_rate_multiplier() -> None:
    score = DistanceScore(light_years_per_second=10.0)
    score.set_rate_multiplier(2.5)
    score.update(2.0)
    assert score.light_years == 50.0


def test_player_moves_up_within_bounds() -> None:
    image = pygame.Surface((64, 64))
    player = Player(image, (50, 100))

    player.update(0.1, FakeKeys({pygame.K_UP}), max_height=600)
    assert player.rect.y == 100 - int(300 * 0.1)


def test_player_stops_at_top() -> None:
    image = pygame.Surface((64, 64))
    player = Player(image, (50, 0))

    player.update(0.1, FakeKeys({pygame.K_UP}), max_height=600)
    assert player.rect.y == 0


def test_player_stops_at_bottom() -> None:
    image = pygame.Surface((64, 64))
    player = Player(image, (50, 600 - 64))

    player.update(0.1, FakeKeys({pygame.K_DOWN}), max_height=600)
    assert player.rect.y == 600 - 64


def test_meteorite_moves_left_without_vertical_change() -> None:
    met = Meteorite(pygame.Rect(800, 100, 44, 44), speed_x=200.0)
    met.update(0.1, player_y=300)
    assert met.rect.x == 800 - round(200.0 * 0.1)
    assert met.rect.y == 100


def test_meteorite_is_off_screen() -> None:
    assert Meteorite(pygame.Rect(-50, 100, 44, 44), 200.0).is_off_screen is True
    assert Meteorite(pygame.Rect(0, 100, 44, 44), 200.0).is_off_screen is False


def test_wave_enemy_moves_left_and_oscillates() -> None:
    enemy = WaveEnemy(pygame.Rect(800, 200, 44, 44), speed_x=180.0)
    enemy.update(0.05, player_y=0)
    assert enemy.rect.x < 800
    assert enemy.rect.y > 200  # erste Halbwelle: sin>0 -> y waechst nach unten


def test_hunter_enemy_moves_toward_player() -> None:
    enemy = HunterEnemy(pygame.Rect(800, 0, 44, 44), speed_x=160.0)
    enemy.update(0.1, player_y=400)
    assert enemy.rect.x < 800
    assert enemy.rect.y > 0  # bewegt sich nach unten Richtung Spieler


def test_hunter_enemy_does_not_overshoot() -> None:
    enemy = HunterEnemy(pygame.Rect(800, 300, 44, 44), speed_x=160.0)  # center y = 322
    enemy.update(1.0, player_y=330)  # nahes Ziel, grosser dt
    assert enemy.rect.centery == 330


def test_collides_with_any() -> None:
    player = pygame.Rect(50, 100, 64, 64)
    hit = Meteorite(pygame.Rect(80, 120, 44, 44), 200.0)
    miss = Meteorite(pygame.Rect(700, 500, 44, 44), 200.0)
    assert collides_with_any(player, [miss, hit]) is True
    assert collides_with_any(player, [miss]) is False
    assert collides_with_any(player, []) is False


def _fake_factory(rng: random.Random, screen_size: tuple[int, int]) -> Meteorite:
    return Meteorite(pygame.Rect(screen_size[0], 0, 10, 10), 100.0)


def test_spawner_no_spawn_before_interval() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    assert spawner.update(0.5) == []


def test_spawner_spawns_after_interval() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    spawner.update(0.5)
    spawned = spawner.update(0.6)
    assert len(spawned) == 1
    assert isinstance(spawned[0], Meteorite)


def test_spawner_multiple_spawns_in_one_update() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    assert len(spawner.update(3.5)) == 3


def test_game_scene_collision_opens_death_screen(context: GameContext) -> None:
    scene = GameScene(context)
    scene.score.light_years = 42.0
    scene.entities.append(Meteorite(pygame.Rect(50, 100, 44, 44), speed_x=0.0))
    scene.update(0.016)
    assert scene._transition is Transition.DEATH_SCREEN
    assert context.state.final_light_years > 42.0


def test_game_scene_removes_off_screen_entities(context: GameContext) -> None:
    scene = GameScene(context)
    scene.entities.append(Meteorite(pygame.Rect(-100, 300, 44, 44), speed_x=0.0))
    scene.update(0.016)
    assert scene.entities == []


def test_game_scene_updates_score(context: GameContext) -> None:
    scene = GameScene(context)
    scene.update(0.5)
    assert scene.score.light_years > 0
