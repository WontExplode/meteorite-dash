"""Reine Regeltests für den adaptiven Director des freien Spielmodus."""

import random

import pygame

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_MIN,
    DIFFICULTY_SPEED_MULTIPLIER_MAX,
)
from meteorite_dash.difficulty import DifficultyParams
from meteorite_dash.entities import AmmoPickup, Meteorite
from meteorite_dash.simulation import RunConfig, Simulation

SEED = 3301


def _sim() -> Simulation:
    return Simulation(RunConfig(SEED, "Allrounder"))


def _meteorite(x: int, y: int) -> Meteorite:
    return Meteorite(
        pygame.Rect(x, y, 20, 20),
        speed_x=100.0,
        hp=10,
        contact_damage=10,
    )


def _drive(
    director: AdaptiveDirector,
    sim: Simulation,
    ticks: int,
    *,
    close_passes: bool = False,
) -> DifficultyParams:
    rng = random.Random(7)
    params = DifficultyParams()
    for tick in range(1, ticks + 1):
        sim.tick = tick
        if tick % 60 == 0:
            # Hinter dem Spieler: y=165 ist knapp, y=400 deutlich sicher.
            sim.entities = [_meteorite(0, 165 if close_passes else 400)]
        else:
            # Eine aktive Gefahr liefert belastbare schadensfreie Spielzeit.
            sim.entities = [_meteorite(700, 300)]
        params = director.params(sim, rng)
    return params


def test_adaptive_director_starts_with_identity_during_grace_period() -> None:
    director = AdaptiveDirector()
    sim = _sim()
    sim.tick = 1

    assert director.params(sim, random.Random(0)) == DifficultyParams()
    assert director.diagnostics.intensity == 0.0


def test_safe_play_reaches_challenge_faster_than_repeated_near_misses() -> None:
    skilled = AdaptiveDirector()
    pressured = AdaptiveDirector()

    skilled_params = _drive(skilled, _sim(), 60 * 45)
    pressured_params = _drive(pressured, _sim(), 60 * 45, close_passes=True)

    assert skilled.diagnostics.safe_passes == 45
    assert pressured.diagnostics.near_misses == 45
    assert skilled.diagnostics.mastery > pressured.diagnostics.mastery
    assert skilled_params.speed_multiplier > pressured_params.speed_multiplier
    assert skilled_params.spawn_interval_multiplier < pressured_params.spawn_interval_multiplier


def test_damage_reduces_intensity_but_preserves_part_of_mastery() -> None:
    director = AdaptiveDirector()
    sim = _sim()
    _drive(director, sim, 60 * 35)
    before = director.diagnostics

    sim.player.hp -= round(sim.player.max_hp * 0.3)
    rng = random.Random(7)
    for tick in range(60 * 35 + 1, 60 * 37 + 1):
        sim.tick = tick
        sim.entities = [_meteorite(700, 300)]
        director.params(sim, rng)
    after = director.diagnostics

    assert after.intensity < before.intensity
    assert 0.0 < after.mastery < before.mastery
    assert after.hold_until_tick > sim.tick


def test_near_miss_is_counted_once_per_entity() -> None:
    director = AdaptiveDirector()
    sim = _sim()
    rng = random.Random(1)
    near = _meteorite(0, 165)
    sim.entities = [near]

    for tick in range(1, 20):
        sim.tick = tick
        director.params(sim, rng)

    assert director.diagnostics.near_misses == 1
    assert director.diagnostics.safe_passes == 0


def test_outputs_stay_within_configured_bounds() -> None:
    director = AdaptiveDirector()
    params = _drive(director, _sim(), 60 * 180)

    assert 1.0 <= params.speed_multiplier <= DIFFICULTY_SPEED_MULTIPLIER_MAX
    assert DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_MIN <= params.spawn_interval_multiplier <= 1.0


def test_same_observations_produce_identical_director_state() -> None:
    first = AdaptiveDirector()
    second = AdaptiveDirector()
    first_sim = _sim()
    second_sim = _sim()
    first_rng = random.Random(11)
    second_rng = random.Random(11)

    for tick in range(1, 60 * 20 + 1):
        first_sim.tick = second_sim.tick = tick
        x = 0 if tick % 90 == 0 else 700
        y = 165 if tick % 180 == 0 else 350
        first_sim.entities = [_meteorite(x, y)]
        second_sim.entities = [_meteorite(x, y)]
        assert first.params(first_sim, first_rng) == second.params(second_sim, second_rng)

    assert first.state_key() == second.state_key()


def test_pickups_do_not_count_as_safe_or_near_passes() -> None:
    director = AdaptiveDirector()
    sim = _sim()
    harmless = AmmoPickup(pygame.Rect(0, 165, 20, 20), 100.0)
    sim.entities = [harmless]
    sim.tick = 1

    director.params(sim, random.Random(0))

    assert director.diagnostics.safe_passes == 0
    assert director.diagnostics.near_misses == 0
