"""Deterministischer Kern (Issue #34): Fixstep, Seed-Streams, Events, Hash, Director-Vertrag."""

import math
import random
from collections.abc import Sequence

import pygame
import pytest

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.coins import Coin, CoinFormation
from meteorite_dash.config import (
    AMMO_RESERVE_BONUS,
    ARMOR_HP_BONUS,
    COIN_RADIUS,
    MAX_STEPS_PER_FRAME,
    SEED_BITS,
    SEED_ENV,
    SHIELD_CHARGES,
    SIM_DT,
    STANDARD_WEAPON_MAX_AMMO,
)
from meteorite_dash.context import GameContext
from meteorite_dash.difficulty import ConstantDirector, DifficultyParams, SimulationView
from meteorite_dash.entities import AmmoPickup, Entity, Meteorite
from meteorite_dash.headless import Trace, run, scripted_inputs
from meteorite_dash.inputs import InputFrame
from meteorite_dash.mathutil import det_hypot, det_sin
from meteorite_dash.mode_directors import director_for_mode
from meteorite_dash.replay import RunMode
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.simulation import (
    EventKind,
    RunConfig,
    SimEvent,
    Simulation,
    pick_seed,
    seeded,
)
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.weapons import WeaponKind, WeaponSpec

SEED = 1234


def _sim(
    seed: int = SEED, ship: str = "Allrounder", accessories: tuple[str, ...] = ()
) -> Simulation:
    return Simulation(RunConfig(seed, ship, accessories))


def _meteorite(rect: pygame.Rect, *, hp: int = 10, contact_damage: int = 15) -> Meteorite:
    return Meteorite(rect, speed_x=0.0, hp=hp, contact_damage=contact_damage)


def _kinds(events: Sequence[SimEvent]) -> list[EventKind]:
    return [event.kind for event in events]


# --- mathutil ---------------------------------------------------------------------


def test_det_sin_matches_libm_closely() -> None:
    for i in range(-400, 400):
        x = i * 0.137
        assert abs(det_sin(x) - math.sin(x)) < 1e-9, x


def test_det_sin_exact_anchors() -> None:
    assert det_sin(0.0) == 0.0
    assert det_sin(math.pi / 2) == pytest.approx(1.0, abs=1e-12)
    assert det_sin(-math.pi / 2) == pytest.approx(-1.0, abs=1e-12)


def test_det_hypot() -> None:
    assert det_hypot(3.0, 4.0) == 5.0
    assert det_hypot(0.0, 0.0) == 0.0


# --- Seeds & Konfiguration ---------------------------------------------------------


def test_seeded_streams_are_reproducible_and_independent() -> None:
    assert seeded(1, "spawn").random() == seeded(1, "spawn").random()
    assert seeded(1, "spawn").random() != seeded(1, "coins").random()
    assert seeded(1, "spawn").random() != seeded(2, "spawn").random()


def test_pick_seed_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SEED_ENV, "42")
    assert pick_seed() == 42
    monkeypatch.setenv(SEED_ENV, "kein-int")
    assert 0 <= pick_seed() < (1 << SEED_BITS)
    monkeypatch.delenv(SEED_ENV)
    assert 0 <= pick_seed() < (1 << SEED_BITS)


def test_run_config_rejects_unknown_catalog_ids() -> None:
    with pytest.raises(ValueError):
        RunConfig(1, "Todesstern")
    with pytest.raises(ValueError):
        RunConfig(1, "Allrounder", ("jetpack",))


def test_run_config_applies_ship_and_accessories() -> None:
    base = _sim(ship="Brawler")
    kitted = _sim(ship="Brawler", accessories=("armor", "ammo_reserve", "shield", "magnet"))
    assert kitted.player.max_hp == base.player.max_hp + ARMOR_HP_BONUS
    assert kitted.loadout.active.ammo == STANDARD_WEAPON_MAX_AMMO + AMMO_RESERVE_BONUS
    assert kitted.shield_charges == SHIELD_CHARGES
    assert kitted.magnet_enabled is True
    assert base.shield_charges == 0
    assert base.magnet_enabled is False


# --- Determinismus -------------------------------------------------------------------


def _long_run(seed: int, input_seed: int = 7, ticks: int = 3000) -> Trace:
    return run(RunConfig(seed, "Allrounder"), scripted_inputs(input_seed, ticks))


def test_same_seed_and_inputs_are_bit_identical() -> None:
    first = _long_run(SEED)
    second = _long_run(SEED)
    assert first.events  # der Lauf tut etwas
    assert first.events == second.events
    assert first.final == second.final
    assert first.state_hash == second.state_hash


def test_different_seed_diverges() -> None:
    assert _long_run(SEED).state_hash != _long_run(SEED + 1).state_hash


def test_different_inputs_diverge() -> None:
    assert _long_run(SEED, input_seed=1).state_hash != _long_run(SEED, input_seed=2).state_hash


def test_trace_snapshots_prove_score_hp_ammo_after_every_interaction() -> None:
    trace = _long_run(SEED, ticks=6000)
    sim = _sim()
    previous = sim.snapshot()
    for event in trace.events:
        snap = event.snapshot
        assert snap.tick >= previous.tick
        assert 0 <= snap.hp <= sim.player.max_hp
        assert 0 <= snap.ammo <= STANDARD_WEAPON_MAX_AMMO
        assert snap.light_years >= previous.light_years
        assert snap.coins >= previous.coins
        if event.kind is EventKind.FIRED:
            assert snap.ammo == previous.ammo - 1 or snap.ammo == STANDARD_WEAPON_MAX_AMMO - 1
        elif event.kind is EventKind.CONTACT:
            assert snap.hp == previous.hp - event.value
        elif event.kind in (EventKind.COIN, EventKind.COIN_BONUS):
            assert snap.coins == previous.coins + event.value
        elif event.kind is EventKind.AMMO_PICKUP:
            assert snap.ammo == STANDARD_WEAPON_MAX_AMMO
        elif event.kind is EventKind.DEATH:
            assert snap.hp == 0
        previous = snap
    assert EventKind.FIRED in _kinds(trace.events)
    assert trace.final.tick >= previous.tick


def test_state_hash_tracks_state() -> None:
    sim = _sim()
    before = sim.state_hash()
    assert before == _sim().state_hash()
    sim.step(InputFrame.NONE)
    assert sim.state_hash() != before


def test_step_after_death_is_noop() -> None:
    sim = _sim()
    sim.entities.append(_meteorite(sim.player.rect.copy(), contact_damage=999))
    assert _kinds(sim.step(InputFrame.NONE))[-1] is EventKind.DEATH
    assert sim.is_over
    tick, digest = sim.tick, sim.state_hash()
    assert sim.step(InputFrame.FIRE) == []
    assert (sim.tick, sim.state_hash()) == (tick, digest)


# --- Events ------------------------------------------------------------------------------


def test_fired_event_carries_ammo_and_sound() -> None:
    sim = _sim()
    events = sim.step(InputFrame.FIRE)
    assert _kinds(events) == [EventKind.FIRED]
    assert events[0].snapshot.ammo == STANDARD_WEAPON_MAX_AMMO - 1
    assert events[0].sound == "standard-gun.mp3"
    # Cooldown: der nächste Tick feuert nicht.
    assert sim.step(InputFrame.FIRE) == []


def test_swap_weapon_is_an_edge_input() -> None:
    sim = _sim(ship="Brawler")
    bonus = WeaponSpec(
        WeaponKind.STANDARD, "Bonus", 3, permanent=False, damage=20, fire_cooldown=0.1
    )
    assert sim.loadout.add_weapon(bonus)
    sim.step(InputFrame.SWAP_WEAPON)
    assert sim.loadout.active_index == 1
    sim.step(InputFrame.NONE)
    assert sim.loadout.active_index == 1


def test_contact_then_death_events() -> None:
    sim = _sim()
    sim.entities.append(_meteorite(sim.player.rect.copy(), contact_damage=30))
    events = sim.step(InputFrame.NONE)
    assert _kinds(events) == [EventKind.CONTACT]
    assert events[0].value == 30
    assert events[0].snapshot.hp == sim.player.max_hp - 30

    sim.entities.append(_meteorite(sim.player.rect.copy(), contact_damage=999))
    events = sim.step(InputFrame.NONE)
    assert _kinds(events) == [EventKind.CONTACT, EventKind.DEATH]
    assert events[-1].snapshot.hp == 0


def test_shield_event_blocks_without_damage() -> None:
    sim = _sim(ship="Brawler", accessories=("shield",))
    sim.entities.append(_meteorite(sim.player.rect.copy(), contact_damage=40))
    events = sim.step(InputFrame.NONE)
    assert _kinds(events) == [EventKind.SHIELD]
    assert events[0].snapshot.shield == SHIELD_CHARGES - 1
    assert sim.player.hp == sim.player.max_hp


def test_ammo_pickup_event() -> None:
    sim = _sim()
    sim.loadout.fire()
    sim.entities.append(AmmoPickup(sim.player.rect.copy(), speed_x=0.0))
    events = sim.step(InputFrame.NONE)
    assert _kinds(events) == [EventKind.AMMO_PICKUP]
    assert events[0].snapshot.ammo == STANDARD_WEAPON_MAX_AMMO


def test_coin_and_bonus_events() -> None:
    sim = _sim()
    coin = Coin(pygame.Rect(50, 100, COIN_RADIUS * 2, COIN_RADIUS * 2), 0.0)
    sim.formations.append(CoinFormation([coin], bonus=5))
    events = sim.step(InputFrame.NONE)
    assert [(e.kind, e.value, e.snapshot.coins) for e in events] == [
        (EventKind.COIN, 1, 1),
        (EventKind.COIN_BONUS, 5, 6),
    ]


def test_hit_and_destroyed_events_in_one_tick() -> None:
    sim = _sim()
    sim.entities.append(_meteorite(pygame.Rect(110, 120, 44, 44), hp=10))
    events = sim.step(InputFrame.FIRE)
    assert _kinds(events) == [EventKind.FIRED, EventKind.HIT, EventKind.DESTROYED]
    assert sim.entities == [] and sim.projectiles == []


# --- Director-Vertrag (#32/#33) ---------------------------------------------------------


class _RecordingDirector:
    def __init__(self, params: DifficultyParams) -> None:
        self._params = params
        self.first_roll: float | None = None
        self.calls = 0

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        self.calls += 1
        if self.first_roll is None:
            self.first_roll = rng.random()
        assert sim.tick >= 1
        return self._params


def test_difficulty_params_reject_non_positive_factors() -> None:
    with pytest.raises(ValueError):
        DifficultyParams(speed_multiplier=0.0)
    with pytest.raises(ValueError):
        DifficultyParams(spawn_interval_multiplier=-1.0)


def test_director_speed_multiplier_scales_horizontal_movement() -> None:
    fast = Simulation(
        RunConfig(SEED, "Allrounder"), director=ConstantDirector(DifficultyParams(2.0))
    )
    slow = _sim()
    for sim in (fast, slow):
        sim.entities.append(
            Meteorite(pygame.Rect(700, 300, 40, 40), 120.0, hp=10, contact_damage=1)
        )
        sim.step(InputFrame.NONE)
    assert fast.entities[0].rect.x == round(700 - 120.0 * 2.0 * SIM_DT)
    assert slow.entities[0].rect.x == round(700 - 120.0 * SIM_DT)


def test_director_speed_multiplier_scales_light_years() -> None:
    fast = Simulation(
        RunConfig(SEED, "Allrounder"), director=ConstantDirector(DifficultyParams(2.0))
    )
    normal = _sim()

    fast.step(InputFrame.NONE)
    normal.step(InputFrame.NONE)

    assert fast.light_years == 2.0 * normal.light_years
    assert fast.score.rate_multiplier == 2.0
    assert normal.score.rate_multiplier == 1.0


def test_coin_cadence_follows_world_speed_not_hazard_density(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sim = Simulation(
        RunConfig(SEED, "Allrounder"),
        director=ConstantDirector(DifficultyParams(2.0, 0.6)),
    )
    hazard_scales: list[float] = []
    coin_scales: list[float] = []

    def update_hazards(
        dt: float,
        accept: object | None = None,
        *,
        interval_scale: float = 1.0,
    ) -> list[Entity]:
        del dt, accept
        hazard_scales.append(interval_scale)
        return []

    def update_coins(
        dt: float,
        accept: object | None = None,
        *,
        interval_scale: float = 1.0,
    ) -> list[CoinFormation]:
        del dt, accept
        coin_scales.append(interval_scale)
        return []

    monkeypatch.setattr(sim.spawner, "update", update_hazards)
    monkeypatch.setattr(sim.coin_spawner, "update", update_coins)

    sim.step(InputFrame.NONE)

    assert hazard_scales == [0.6]
    assert coin_scales == [0.5]


def test_spawner_interval_scale_densifies_spawns() -> None:
    def factory(rng: random.Random, area: tuple[int, int]) -> int:
        return 1

    dense = Spawner([SpawnEntry(1.0, factory)], (800, 600), random.Random(0), (1.0, 1.0))
    sparse = Spawner([SpawnEntry(1.0, factory)], (800, 600), random.Random(0), (1.0, 1.0))
    assert len(dense.update(0.5, interval_scale=0.5)) == 1
    assert len(sparse.update(0.5)) == 0


def test_director_gets_own_rng_stream_every_tick() -> None:
    director = _RecordingDirector(DifficultyParams())
    sim = Simulation(RunConfig(SEED, "Allrounder"), director=director)
    for _ in range(10):
        sim.step(InputFrame.NONE)
    assert director.calls == 10
    assert director.first_roll == seeded(SEED, "director").random()


def test_director_keeps_replays_bit_identical() -> None:
    params = DifficultyParams(speed_multiplier=1.5, spawn_interval_multiplier=0.7)

    def trace() -> Trace:
        return run(
            RunConfig(SEED, "Allrounder"),
            scripted_inputs(3, 2000),
            director=ConstantDirector(params),
        )

    first, second = trace(), trace()
    assert first.state_hash == second.state_hash
    assert first.state_hash != _long_run(SEED, input_seed=3, ticks=2000).state_hash


def test_state_hash_contains_stateful_director() -> None:
    first_director = AdaptiveDirector()
    second_director = AdaptiveDirector()
    first = Simulation(RunConfig(SEED, "Allrounder"), director=first_director)
    second = Simulation(RunConfig(SEED, "Allrounder"), director=second_director)
    first.tick = second.tick = 1

    first_director.params(first, random.Random(0))

    assert first.snapshot() == second.snapshot()
    assert first.difficulty == second.difficulty
    assert first.state_hash() != second.state_hash()


# --- Szene: fester Zeitschritt, Fensterunabhängigkeit ---------------------------------------


def test_scene_uses_run_config_from_state(context: GameContext) -> None:
    scene = GameScene(context, seed=5)
    assert scene.sim.config == RunConfig(5, "Allrounder", ())
    assert 0 <= GameScene(context).seed < (1 << SEED_BITS)


def test_scene_steps_in_fixed_ticks(context: GameContext) -> None:
    scene = GameScene(context, seed=1)
    scene.update(3 * SIM_DT)
    assert scene.sim.tick == 3
    scene.update(0.4 * SIM_DT)
    assert scene.sim.tick == 3
    scene.update(0.6 * SIM_DT)
    assert scene.sim.tick == 4


def test_scene_caps_steps_per_frame(context: GameContext) -> None:
    scene = GameScene(context, seed=1)
    scene.update(1.0)
    assert scene.sim.tick == MAX_STEPS_PER_FRAME
    assert scene._accumulator == 0.0


def test_scene_swap_edge_is_consumed_once(context: GameContext) -> None:
    context.state.selected_ship_index = 2  # Brawler: 3 Waffenslots
    scene = GameScene(context, seed=1)
    bonus = WeaponSpec(
        WeaponKind.STANDARD, "Bonus", 3, permanent=False, damage=20, fire_cooldown=0.1
    )
    assert scene.sim.loadout.add_weapon(bonus)
    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
    scene.update(2 * SIM_DT)
    assert scene.sim.loadout.active_index == 1


def test_scene_toggles_hidden_difficulty_debug_hud(context: GameContext) -> None:
    scene = GameScene(context, seed=1)
    assert not scene._show_difficulty_debug

    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F3))

    assert scene._show_difficulty_debug
    lines = scene._difficulty_debug_lines()
    assert lines[0] == "DEBUG FREE ADAPTIVE"
    assert lines[1] == "TICK 000000"
    assert lines[2] == "SPEED x1.000 SPAWN x1.000"
    assert lines[3] == "HP 100/100 AMMO 7/7"
    state_hash = scene.sim.state_hash()
    context.apply_resize((1280, 720))
    scene.draw()
    assert scene.sim.state_hash() == state_hash

    scene.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F3))
    assert not scene._show_difficulty_debug


def _drive(scene: GameScene, ticks: int) -> str:
    for index, frame in enumerate(scripted_inputs(11, ticks)):
        scene.step(frame)
        if index % 97 == 0:
            scene.draw()  # Zeichnen darf den Zustand nie anfassen
    return scene.sim.state_hash()


def test_scene_is_window_independent_and_matches_headless(context: GameContext) -> None:
    ticks = 900
    hashes = set()
    for size in ((800, 600), (1600, 1200), (320, 240), (1600, 600)):
        context.apply_resize(size)
        hashes.add(_drive(GameScene(context, seed=SEED), ticks))
    assert len(hashes) == 1
    headless = run(
        RunConfig(SEED, "Allrounder"),
        scripted_inputs(11, ticks),
        director=director_for_mode(RunMode.FREE),
    )
    assert hashes == {headless.state_hash}


def test_scene_death_sets_final_state(context: GameContext) -> None:
    scene = GameScene(context, seed=1)
    scene.sim.score.light_years = 42.0
    scene.sim.coins_collected = 3
    scene.sim.entities.append(_meteorite(scene.sim.player.rect.copy(), contact_damage=999))
    scene.update(SIM_DT)
    assert scene._transition is Transition.DEATH_SCREEN
    assert context.state.final_light_years > 42.0
    assert context.state.final_coins == 3


def test_scene_plays_bonus_notice_from_event(context: GameContext) -> None:
    scene = GameScene(context, seed=1)
    coin = Coin(pygame.Rect(50, 100, COIN_RADIUS * 2, COIN_RADIUS * 2), 0.0)
    scene.sim.formations.append(CoinFormation([coin], bonus=8))
    scene.step(InputFrame.NONE)
    assert scene._bonus_notice == "BONUS +8"
    assert scene._bonus_notice_ttl > 0
