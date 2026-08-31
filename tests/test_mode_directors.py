"""Trennung der Schwierigkeitsstrategien für Free und Daily."""

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    ADAPTIVE_DIRECTOR_VERSION,
    CONSTANT_DIRECTOR_VERSION,
    DIFFICULTY_SPEED_MULTIPLIER_CAP,
    RAMP_DIRECTOR_VERSION,
)
from meteorite_dash.difficulty import CompositeDirector, ConstantDirector, DirectorKind
from meteorite_dash.mode_directors import (
    director_for_kind,
    director_for_mode,
    director_kind_for_mode,
    director_version_for_kind,
    director_version_for_mode,
)
from meteorite_dash.ramp_difficulty import RampDirector
from meteorite_dash.replay import RunMode


def test_free_mode_gets_fresh_adaptive_directors_on_the_ramp() -> None:
    first = director_for_mode(RunMode.FREE)
    second = director_for_mode(RunMode.FREE)

    assert isinstance(first, CompositeDirector)
    assert isinstance(second, CompositeDirector)
    assert first is not second
    # Rampe trägt die Laufzeit, der adaptive Teil moduliert um sie herum.
    assert [type(part) for part in first.directors] == [RampDirector, AdaptiveDirector]
    assert first.directors[1] is not second.directors[1]


def test_daily_mode_gets_the_plain_time_ramp() -> None:
    first = director_for_mode(RunMode.DAILY)
    second = director_for_mode(RunMode.DAILY)

    assert isinstance(first, RampDirector)
    assert isinstance(second, RampDirector)
    assert first is not second


def test_director_versions_are_separate_per_mode() -> None:
    assert director_kind_for_mode(RunMode.FREE) is DirectorKind.ADAPTIVE
    assert director_kind_for_mode(RunMode.DAILY) is DirectorKind.RAMP
    assert director_version_for_mode(RunMode.FREE) == ADAPTIVE_DIRECTOR_VERSION
    assert director_version_for_mode(RunMode.DAILY) == RAMP_DIRECTOR_VERSION
    assert director_version_for_kind(DirectorKind.ADAPTIVE) == ADAPTIVE_DIRECTOR_VERSION
    assert director_version_for_kind(DirectorKind.RAMP) == RAMP_DIRECTOR_VERSION
    assert director_version_for_kind(DirectorKind.CONSTANT) == CONSTANT_DIRECTOR_VERSION
    assert isinstance(director_for_kind(DirectorKind.CONSTANT), ConstantDirector)


def test_free_mode_shares_the_same_ceiling_as_daily() -> None:
    """Rampe mal adaptiv darf nicht über den gemeinsamen Deckel hinausschießen."""
    free = director_for_kind(DirectorKind.ADAPTIVE)
    assert isinstance(free, CompositeDirector)
    assert free._speed_cap == DIFFICULTY_SPEED_MULTIPLIER_CAP
