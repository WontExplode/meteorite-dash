import random

import pygame
import pytest

from meteorite_dash.coins import (
    LAYOUTS,
    Coin,
    CoinFormation,
    Pickup,
    coin_rects,
    is_clear,
    layout_for,
    spawn_coin_formation,
)
from meteorite_dash.config import (
    COIN_BONUS_NOTICE_SECONDS,
    COIN_COLOR,
    COIN_HAZARD_CLEARANCE,
    COIN_PATTERNS,
    COIN_RADIUS,
    COIN_SPAWN_INTERVAL_RANGE,
    CoinPatternSpec,
)
from meteorite_dash.context import GameContext
from meteorite_dash.entities import AmmoPickup, Meteorite
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.score import format_coins

DIAMETER = COIN_RADIUS * 2


def _coin(x: int, y: int, speed_x: float = 0.0) -> Coin:
    return Coin(pygame.Rect(x, y, DIAMETER, DIAMETER), speed_x)


def _pattern(name: str, bonus: int = 5) -> CoinPatternSpec:
    return CoinPatternSpec(name, 1.0, bonus)


def _meteorite(x: int, y: int, size: int = 60) -> Meteorite:
    return Meteorite(pygame.Rect(x, y, size, size), speed_x=0.0, hp=10, contact_damage=15)


# --- Layouts ---------------------------------------------------------------


def test_every_configured_pattern_has_a_layout() -> None:
    for pattern in COIN_PATTERNS:
        assert pattern.name in LAYOUTS, pattern.name


def test_layout_for_rejects_unknown_name() -> None:
    with pytest.raises(ValueError):
        layout_for("hexagon")


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_layouts_are_deterministic_and_left_to_right(name: str) -> None:
    layout = layout_for(name)
    first = layout(random.Random(7))
    second = layout(random.Random(7))
    assert first == second
    assert len(first) >= 2
    assert first[0][0] == 0.0
    dxs = [dx for dx, _ in first]
    assert dxs == sorted(dxs)


def test_zigzag_has_two_peaks() -> None:
    offsets = layout_for("zigzag")(random.Random(0))
    dys = [abs(dy) for _, dy in offsets]
    peaks = [i for i in range(1, len(dys) - 1) if dys[i - 1] < dys[i] > dys[i + 1]]
    assert len(peaks) == 2
    assert dys[0] == dys[-1] == 0.0


def test_diamond_is_symmetric() -> None:
    offsets = layout_for("diamond")(random.Random(0))
    assert len(offsets) == 9
    assert sum(dy for _, dy in offsets) == 0.0


# --- Spawn -----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(LAYOUTS))
@pytest.mark.parametrize("seed", range(5))
def test_spawn_coin_formation_fits_on_screen(name: str, seed: int) -> None:
    width, height = 800, 600
    formation = spawn_coin_formation(random.Random(seed), (width, height), pattern=_pattern(name))
    assert formation.coins
    for coin in formation.coins:
        assert coin.rect.x >= width  # startet rechts außerhalb
        assert 0 <= coin.rect.y <= height - DIAMETER
        assert coin.rect.size == (DIAMETER, DIAMETER)


def test_spawn_coin_formation_carries_pattern_bonus() -> None:
    formation = spawn_coin_formation(random.Random(0), (800, 600), pattern=_pattern("line", 9))
    assert formation.bonus == 9


def test_spawn_coin_formation_scales_size_and_spread() -> None:
    base = spawn_coin_formation(random.Random(3), (800, 600), pattern=_pattern("wave"))
    scaled = spawn_coin_formation(
        random.Random(3), (1600, 1200), pattern=_pattern("wave"), sx=2.0, sy=2.0, su=2.0
    )
    assert scaled.coins[0].rect.size == (DIAMETER * 2, DIAMETER * 2)
    assert scaled.coins[0].speed_x == base.coins[0].speed_x * 2

    def spread(formation: CoinFormation) -> tuple[int, int]:
        xs = [c.rect.x for c in formation.coins]
        ys = [c.rect.y for c in formation.coins]
        return max(xs) - min(xs), max(ys) - min(ys)

    base_dx, base_dy = spread(base)
    scaled_dx, scaled_dy = spread(scaled)
    assert scaled_dx == base_dx * 2
    assert abs(scaled_dy - base_dy * 2) <= 2  # Rundung je Münze


def test_spawn_coin_formation_survives_tiny_window() -> None:
    formation = spawn_coin_formation(random.Random(0), (100, 40), pattern=_pattern("diamond"))
    assert len(formation.coins) == 9


# --- Coin & Formation --------------------------------------------------------


def test_coin_does_not_damage_player() -> None:
    assert _coin(0, 0).damages_player is False


def test_coin_moves_left_without_vertical_change() -> None:
    coin = _coin(800, 100, speed_x=200.0)
    coin.update(0.1, player_y=300)
    assert coin.rect.x == 800 - round(200.0 * 0.1)
    assert coin.rect.y == 100


def test_coin_draw_paints_coin_color_at_center() -> None:
    surface = pygame.Surface((DIAMETER, DIAMETER))
    _coin(0, 0).draw(surface)
    assert surface.get_at((COIN_RADIUS, COIN_RADIUS))[:3] == COIN_COLOR


def test_pickup_total() -> None:
    assert Pickup(3, 5).total == 8


def test_formation_collect_removes_hit_coins_only() -> None:
    formation = CoinFormation([_coin(50, 100), _coin(700, 500)], bonus=5)
    pickup = formation.collect(pygame.Rect(50, 100, 64, 64))
    assert pickup == Pickup(1, 0)
    assert formation.collected == 1
    assert len(formation.coins) == 1
    assert formation.is_finished is False


def test_formation_pays_bonus_when_completed() -> None:
    formation = CoinFormation([_coin(50, 100), _coin(90, 100)], bonus=5)
    assert formation.collect(pygame.Rect(50, 100, 30, 30)) == Pickup(1, 0)
    assert formation.collect(pygame.Rect(90, 100, 30, 30)) == Pickup(1, 5)
    assert formation.is_finished is True
    # Danach nichts mehr zu holen — kein doppelter Bonus.
    assert formation.collect(pygame.Rect(0, 0, 800, 600)) == Pickup(0, 0)


def test_formation_no_bonus_after_missed_coin() -> None:
    formation = CoinFormation([_coin(-100, 100), _coin(50, 100)], bonus=5)
    formation.update(0.0, player_y=0)
    assert formation.missed == 1
    assert formation.collect(pygame.Rect(50, 100, 30, 30)) == Pickup(1, 0)
    assert formation.is_finished is True


def test_formation_all_missed_is_finished_without_bonus() -> None:
    formation = CoinFormation([_coin(-100, 100), _coin(-60, 100)], bonus=5)
    formation.update(0.0, player_y=0)
    assert formation.is_finished is True
    assert formation.collect(pygame.Rect(0, 0, 800, 600)) == Pickup(0, 0)


# --- GameScene -------------------------------------------------------------


def test_game_scene_collects_coins_without_dying(context: GameContext) -> None:
    scene = GameScene(context)
    scene.formations.append(CoinFormation([_coin(50, 100)], bonus=5))
    scene.update(0.016)
    assert scene.coins_collected == 1 + 5
    assert scene.formations == []
    assert scene._transition is None
    assert scene._bonus_notice == "BONUS +5"
    assert 0 < scene._bonus_notice_ttl <= COIN_BONUS_NOTICE_SECONDS


def test_game_scene_keeps_unreached_formations(context: GameContext) -> None:
    scene = GameScene(context)
    scene.formations.append(CoinFormation([_coin(700, 500)], bonus=5))
    scene.update(0.016)
    assert scene.coins_collected == 0
    assert len(scene.formations) == 1


def test_game_scene_coin_spawner_yields_formations(context: GameContext) -> None:
    scene = GameScene(context)
    spawned = scene.coin_spawner.update(COIN_SPAWN_INTERVAL_RANGE[1] + 0.1)
    assert spawned
    assert all(isinstance(f, CoinFormation) and f.coins for f in spawned)


def test_game_scene_adds_spawned_formations(
    context: GameContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = GameScene(context)
    formation = CoinFormation([_coin(700, 500)], bonus=5)
    monkeypatch.setattr(scene.coin_spawner, "update", lambda dt, accept=None: [formation])
    scene.update(0.016)
    assert scene.formations == [formation]


# --- Spawn-Ausschluss Münzen <-> Gefahren -------------------------------------


def test_coin_rects_collects_all_remaining_coins() -> None:
    first = CoinFormation([_coin(0, 0), _coin(40, 0)], bonus=1)
    second = CoinFormation([_coin(80, 0)], bonus=1)
    assert coin_rects([first, second]) == [c.rect for c in [*first.coins, *second.coins]]
    assert coin_rects([]) == []


def test_is_clear_respects_clearance() -> None:
    coin = pygame.Rect(100, 100, DIAMETER, DIAMETER)
    near = pygame.Rect(coin.right + 5, 100, 60, 60)
    assert is_clear([coin], [near], clearance=0) is True
    assert is_clear([coin], [near], clearance=8) is False
    assert is_clear([coin], [], clearance=50) is True


def test_game_scene_rejects_hazard_spawned_inside_coin_pattern(context: GameContext) -> None:
    scene = GameScene(context)
    scene.formations.append(CoinFormation([_coin(800, 300)], bonus=5))
    assert scene._accept_entity(_meteorite(800, 300)) is False
    assert scene._accept_entity(_meteorite(800, 0)) is True
    # Harmlose Pickups dürfen auf Münzen liegen.
    ammo = AmmoPickup(pygame.Rect(800, 300, 24, 24), speed_x=0.0)
    assert scene._accept_entity(ammo) is True


def test_game_scene_rejects_coin_pattern_spawned_inside_hazard(context: GameContext) -> None:
    scene = GameScene(context)
    scene.entities.append(_meteorite(780, 280))
    clearance = COIN_HAZARD_CLEARANCE
    assert scene._accept_formation(CoinFormation([_coin(800, 300)], bonus=5)) is False
    assert scene._accept_formation(CoinFormation([_coin(800, 300 + 60 + clearance + 1)], 5))


def test_game_scene_spawn_never_overlaps_coins(context: GameContext) -> None:
    # Volle Münz-Wand am rechten Rand: kein Gefahren-Spawn darf durchkommen.
    scene = GameScene(context)
    wall = [_coin(800, y) for y in range(0, 600, DIAMETER)]
    scene.formations.append(CoinFormation(wall, bonus=0))
    scene.entities.clear()
    spawned = scene.spawner.update(10.0, accept=scene._accept_entity)
    assert all(not entity.damages_player for entity in spawned)


def test_game_scene_draws_coins_above_hazards(context: GameContext) -> None:
    scene = GameScene(context)
    scene.entities.append(_meteorite(400 - 30, 300 - 30))
    scene.formations.append(CoinFormation([_coin(400 - COIN_RADIUS, 300 - COIN_RADIUS)], 1))
    scene.draw()
    assert context.screen.get_at((400, 300))[:3] == COIN_COLOR


def test_game_scene_death_records_final_coins(context: GameContext) -> None:
    scene = GameScene(context)
    scene.coins_collected = 7
    scene.entities.append(
        Meteorite(scene.player.rect.copy(), speed_x=0.0, hp=10, contact_damage=999)
    )
    scene.update(0.016)
    assert scene._transition is Transition.DEATH_SCREEN
    assert context.state.final_coins == 7


def test_game_scene_credits_session_total_on_exit(context: GameContext) -> None:
    context.state.total_coins = 10
    scene = GameScene(context)
    scene.coins_collected = 7
    scene.on_exit()
    assert context.state.total_coins == 17


def test_format_coins() -> None:
    assert format_coins(42) == "0042"
    assert format_coins(12345) == "12345"
