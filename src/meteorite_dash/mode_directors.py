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
from meteorite_dash.difficulty import ConstantDirector, Director
from meteorite_dash.replay import RunMode


def director_for_mode(mode: RunMode) -> Director:
    """Erzeugt für jeden Lauf eine frische Director-Instanz."""
    if mode is RunMode.FREE:
        return AdaptiveDirector()
    if mode is RunMode.DAILY:
        return ConstantDirector()
    raise ValueError(f"Unbekannter Spielmodus: {mode!r}")


def director_version_for_mode(mode: RunMode) -> int:
    """Regelversion des Modus, unabhängig von der gemeinsamen SIM_VERSION."""
    if mode is RunMode.FREE:
        return ADAPTIVE_DIRECTOR_VERSION
    if mode is RunMode.DAILY:
        return CONSTANT_DIRECTOR_VERSION
    raise ValueError(f"Unbekannter Spielmodus: {mode!r}")
