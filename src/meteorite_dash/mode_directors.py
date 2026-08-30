"""Zentrale, seiteneffektfreie Director-Auswahl pro Spielmodus.

Der freie Modus erhält den adaptiven Director. Der Daily Run behält in diesem
Feature-Stack ausdrücklich den bisherigen konstanten Director; seine spätere
feste Zeitrampe kann unabhängig an genau dieser Grenze ergänzt werden.
"""

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    ADAPTIVE_DIRECTOR_VERSION,
    CONSTANT_DIRECTOR_VERSION,
)
from meteorite_dash.difficulty import ConstantDirector, Director, DirectorKind
from meteorite_dash.replay import RunMode


def director_kind_for_mode(mode: RunMode) -> DirectorKind:
    """Ordnet jedem Spielmodus genau eine replay-stabile Strategie zu."""
    if mode is RunMode.FREE:
        return DirectorKind.ADAPTIVE
    if mode is RunMode.DAILY:
        return DirectorKind.CONSTANT
    raise ValueError(f"Unbekannter Spielmodus: {mode!r}")


def director_for_kind(kind: DirectorKind) -> Director:
    """Erzeugt für jeden Lauf eine frische Director-Instanz."""
    if kind is DirectorKind.ADAPTIVE:
        return AdaptiveDirector()
    if kind is DirectorKind.CONSTANT:
        return ConstantDirector()
    raise ValueError(f"Unbekannte Director-Art: {kind!r}")


def director_version_for_kind(kind: DirectorKind) -> int:
    """Regelversion der Strategie, unabhängig von der gemeinsamen SIM_VERSION."""
    if kind is DirectorKind.ADAPTIVE:
        return ADAPTIVE_DIRECTOR_VERSION
    if kind is DirectorKind.CONSTANT:
        return CONSTANT_DIRECTOR_VERSION
    raise ValueError(f"Unbekannte Director-Art: {kind!r}")


def director_for_mode(mode: RunMode) -> Director:
    return director_for_kind(director_kind_for_mode(mode))


def director_version_for_mode(mode: RunMode) -> int:
    return director_version_for_kind(director_kind_for_mode(mode))
