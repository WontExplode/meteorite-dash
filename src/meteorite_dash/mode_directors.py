"""Zentrale, seiteneffektfreie Director-Auswahl pro Spielmodus.

Beide Modi laufen auf der Zeitrampe (`ramp_difficulty.py`): das Welttempo
steigt mit der Laufzeit bis zur gemeinsamen Obergrenze. Der Daily Run nimmt sie
pur — gleiche Laufzeit heißt für alle dasselbe Tempo. Der freie Modus legt den
adaptiven Director darüber, der die Rampe nach Können nach oben oder unten
moduliert; das Produkt deckelt der `CompositeDirector`.
"""

from meteorite_dash.adaptive_difficulty import AdaptiveDirector
from meteorite_dash.config import (
    ADAPTIVE_DIRECTOR_VERSION,
    CONSTANT_DIRECTOR_VERSION,
    DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR,
    DIFFICULTY_SPEED_MULTIPLIER_CAP,
    RAMP_DIRECTOR_VERSION,
)
from meteorite_dash.difficulty import (
    CompositeDirector,
    ConstantDirector,
    Director,
    DirectorKind,
)
from meteorite_dash.ramp_difficulty import RampDirector
from meteorite_dash.replay import RunMode


def director_kind_for_mode(mode: RunMode) -> DirectorKind:
    """Ordnet jedem Spielmodus genau eine replay-stabile Strategie zu."""
    if mode is RunMode.FREE:
        return DirectorKind.ADAPTIVE
    if mode is RunMode.DAILY:
        return DirectorKind.RAMP
    raise ValueError(f"Unbekannter Spielmodus: {mode!r}")


def director_for_kind(kind: DirectorKind) -> Director:
    """Erzeugt für jeden Lauf eine frische Director-Instanz."""
    if kind is DirectorKind.ADAPTIVE:
        return CompositeDirector(
            RampDirector(),
            AdaptiveDirector(),
            speed_cap=DIFFICULTY_SPEED_MULTIPLIER_CAP,
            interval_floor=DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR,
        )
    if kind is DirectorKind.RAMP:
        return RampDirector()
    if kind is DirectorKind.CONSTANT:
        return ConstantDirector()
    raise ValueError(f"Unbekannte Director-Art: {kind!r}")


def director_version_for_kind(kind: DirectorKind) -> int:
    """Regelversion der Strategie, unabhängig von der gemeinsamen SIM_VERSION."""
    if kind is DirectorKind.ADAPTIVE:
        return ADAPTIVE_DIRECTOR_VERSION
    if kind is DirectorKind.RAMP:
        return RAMP_DIRECTOR_VERSION
    if kind is DirectorKind.CONSTANT:
        return CONSTANT_DIRECTOR_VERSION
    raise ValueError(f"Unbekannte Director-Art: {kind!r}")


def director_for_mode(mode: RunMode) -> Director:
    return director_for_kind(director_kind_for_mode(mode))


def director_version_for_mode(mode: RunMode) -> int:
    return director_version_for_kind(director_kind_for_mode(mode))
