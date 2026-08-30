"""Trennung der Schwierigkeitsstrategien für Free und Daily."""

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    ADAPTIVE_DIRECTOR_VERSION,
    CONSTANT_DIRECTOR_VERSION,
)
from meteorite_dash.difficulty import ConstantDirector, DirectorKind
from meteorite_dash.mode_directors import (
    director_for_kind,
    director_for_mode,
    director_kind_for_mode,
    director_version_for_kind,
    director_version_for_mode,
)
from meteorite_dash.replay import RunMode


def test_free_mode_gets_fresh_adaptive_directors() -> None:
    first = director_for_mode(RunMode.FREE)
    second = director_for_mode(RunMode.FREE)

    assert isinstance(first, AdaptiveDirector)
    assert isinstance(second, AdaptiveDirector)
    assert first is not second


def test_daily_mode_keeps_fresh_constant_directors() -> None:
    first = director_for_mode(RunMode.DAILY)
    second = director_for_mode(RunMode.DAILY)

    assert isinstance(first, ConstantDirector)
    assert isinstance(second, ConstantDirector)
    assert first is not second


def test_director_versions_are_separate_per_mode() -> None:
    assert director_kind_for_mode(RunMode.FREE) is DirectorKind.ADAPTIVE
    assert director_kind_for_mode(RunMode.DAILY) is DirectorKind.CONSTANT
    assert director_version_for_mode(RunMode.FREE) == ADAPTIVE_DIRECTOR_VERSION
    assert director_version_for_mode(RunMode.DAILY) == CONSTANT_DIRECTOR_VERSION
    assert director_version_for_kind(DirectorKind.ADAPTIVE) == ADAPTIVE_DIRECTOR_VERSION
    assert director_version_for_kind(DirectorKind.CONSTANT) == CONSTANT_DIRECTOR_VERSION
    assert isinstance(director_for_kind(DirectorKind.ADAPTIVE), AdaptiveDirector)
    assert isinstance(director_for_kind(DirectorKind.CONSTANT), ConstantDirector)
