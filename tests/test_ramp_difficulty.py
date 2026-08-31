"""Zeitrampe (Issue #32): Welttempo steigt mit der Laufzeit, in beiden Modi."""

import random

import pytest

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    DIFFICULTY_RAMP_FULL_SECONDS,
    DIFFICULTY_RAMP_GRACE_SECONDS,
    DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX,
    DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR,
    DIFFICULTY_SPEED_MULTIPLIER_CAP,
    SIM_TICKS_PER_SECOND,
)
from meteorite_dash.difficulty import (
    CompositeDirector,
    ConstantDirector,
    DifficultyParams,
    DirectorKind,
    StatefulDirector,
)
from meteorite_dash.headless import run, scripted_inputs
from meteorite_dash.inputs import InputFrame
from meteorite_dash.mode_directors import director_for_kind
from meteorite_dash.ramp_difficulty import RampDirector, ramp_params, ramp_speed
from meteorite_dash.simulation import RunConfig, Simulation

CONFIG = RunConfig(seed=4711, ship="Allrounder")


def _ticks(seconds: float) -> int:
    return round(seconds * SIM_TICKS_PER_SECOND)


# --- Rampe ----------------------------------------------------------------------


def test_ramp_starts_flat_and_then_climbs() -> None:
    assert ramp_speed(0) == 1.0
    assert ramp_speed(_ticks(DIFFICULTY_RAMP_GRACE_SECONDS)) == 1.0
    assert ramp_speed(_ticks(DIFFICULTY_RAMP_GRACE_SECONDS + 1)) > 1.0


def test_ramp_is_monotone_and_capped() -> None:
    previous = 0.0
    for seconds in range(0, 3600, 15):
        speed = ramp_speed(_ticks(seconds))
        assert speed >= previous
        assert 1.0 <= speed <= DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX
        previous = speed
    assert ramp_speed(_ticks(DIFFICULTY_RAMP_FULL_SECONDS)) == pytest.approx(
        DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX
    )
    # Danach bleibt sie stehen, sie läuft nicht weiter.
    assert ramp_speed(_ticks(DIFFICULTY_RAMP_FULL_SECONDS * 3)) == pytest.approx(
        DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX
    )


def test_ramp_keeps_hazard_spacing_constant() -> None:
    """Doppeltes Tempo bei halbem Spawn-Intervall: schneller, nicht leerer."""
    params = ramp_params(_ticks(600))
    assert params.spawn_interval_multiplier == pytest.approx(1.0 / params.speed_multiplier)


def test_ramp_step_up_is_slow() -> None:
    """Die erste Minute darf sich nicht wie ein anderes Spiel anfühlen."""
    assert ramp_speed(_ticks(60)) < 1.3
    assert ramp_speed(_ticks(300)) < 3.0


def test_ramp_director_depends_only_on_the_tick() -> None:
    director = RampDirector()
    sim = Simulation(CONFIG)
    sim.tick = _ticks(120)
    first = director.params(sim, random.Random(1))
    second = director.params(sim, random.Random(999))
    assert first == second
    # Zustandslos: er trägt nichts zum Simulationshash bei.
    assert not isinstance(director, StatefulDirector)


# --- Komposition -----------------------------------------------------------------


def test_composite_multiplies_and_caps() -> None:
    slow = ConstantDirector(DifficultyParams(4.0, 0.5))
    fast = ConstantDirector(DifficultyParams(4.0, 0.5))
    composite = CompositeDirector(slow, fast, speed_cap=10.0, interval_floor=0.3)
    params = composite.params(Simulation(CONFIG), random.Random(0))
    assert params.speed_multiplier == 10.0  # 16.0 gedeckelt
    assert params.spawn_interval_multiplier == 0.3  # 0.25 angehoben


def test_composite_needs_at_least_one_director() -> None:
    with pytest.raises(ValueError):
        CompositeDirector(speed_cap=10.0, interval_floor=0.1)


def test_composite_state_key_only_covers_stateful_parts() -> None:
    composite = CompositeDirector(
        RampDirector(),
        AdaptiveDirector(),
        speed_cap=DIFFICULTY_SPEED_MULTIPLIER_CAP,
        interval_floor=DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR,
    )
    assert len(composite.state_key()) == 1  # nur der adaptive Teil
    assert isinstance(composite, StatefulDirector)


# --- In der Simulation ------------------------------------------------------------


def test_daily_run_gets_faster_over_time() -> None:
    """Der Daily-Director ist die pure Rampe: gleiche Laufzeit, gleiches Tempo für alle."""
    director = director_for_kind(DirectorKind.RAMP)
    sim = Simulation(CONFIG)
    rng = random.Random(0)

    sim.tick = _ticks(DIFFICULTY_RAMP_GRACE_SECONDS)
    early = director.params(sim, rng)
    sim.tick = _ticks(DIFFICULTY_RAMP_GRACE_SECONDS + 120)
    later = director.params(sim, rng)

    assert early == ramp_params(_ticks(DIFFICULTY_RAMP_GRACE_SECONDS))
    assert early.speed_multiplier == 1.0
    assert later.speed_multiplier > early.speed_multiplier


def test_simulation_applies_the_ramp_every_tick() -> None:
    """Die Simulation übernimmt die Stellgrößen unverändert, solange der Lauf läuft.

    Bewusst ohne Überlebens-Annahme: wer nichts tut, stirbt nach gut zehn
    Sekunden, und nach dem Tod ist `step` ein No-op. Ein Test, der auf einen
    langen Lauf baut, misst die Spawn-Folge des Seeds, nicht die Rampe.
    """
    sim = Simulation(CONFIG, director=director_for_kind(DirectorKind.RAMP))
    assert sim.difficulty == ramp_params(0)

    limit = _ticks(DIFFICULTY_RAMP_GRACE_SECONDS + 120)
    while not sim.is_over and sim.tick < limit:
        sim.step(InputFrame.NONE)
        assert sim.difficulty == ramp_params(sim.tick)

    assert sim.tick > 0


def test_score_rate_follows_the_ramp() -> None:
    """Wer länger überlebt, sammelt Lichtjahre schneller — das Tempo zählt mit."""
    sim = Simulation(CONFIG, director=director_for_kind(DirectorKind.RAMP))
    for _ in range(_ticks(600)):
        sim.step(InputFrame.NONE)
        if sim.is_over:
            break
    assert sim.score.rate_multiplier == pytest.approx(sim.difficulty.speed_multiplier)


def test_ramped_run_stays_deterministic() -> None:
    """Gleiche Eingaben, gleicher Seed, gleicher Hash — auch mit Rampe."""
    inputs = list(scripted_inputs(3, 900))
    first = run(CONFIG, inputs, director=director_for_kind(DirectorKind.RAMP))
    second = run(CONFIG, inputs, director=director_for_kind(DirectorKind.RAMP))
    assert first.state_hash == second.state_hash
    assert first.final == second.final


def test_free_mode_never_exceeds_the_shared_ceiling() -> None:
    director = director_for_kind(DirectorKind.ADAPTIVE)
    sim = Simulation(CONFIG, director=director)
    sim.tick = _ticks(DIFFICULTY_RAMP_FULL_SECONDS * 2)  # Rampe längst am Anschlag
    params = director.params(sim, random.Random(0))
    assert params.speed_multiplier <= DIFFICULTY_SPEED_MULTIPLIER_CAP
    assert params.spawn_interval_multiplier >= DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR
