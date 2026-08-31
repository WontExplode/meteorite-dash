"""Zeitrampe (Issue #32): das Welttempo steigt mit der Laufzeit — in jedem Modus.

Der Director ist zustandslos und leitet alles aus `sim.tick` ab: gleiche
Laufzeit heißt gleiche Rampe, unabhängig davon, wie gut jemand spielt. Damit
trägt er das langfristige „es wird immer schneller“, während der adaptive
Director (`adaptive_difficulty.py`) nur noch um ihn herum moduliert.

Die Rampe verkürzt die Spawn-Intervalle um denselben Faktor, um den sie das
Tempo erhöht. Ohne das würden Gefahren bei doppeltem Tempo auch doppelt so weit
auseinanderliegen — das Bild würde leerer statt schwerer. Münzen rechnet
`Simulation._update_coins` bereits genauso.
"""

import random

from meteorite_dash.config import (
    DIFFICULTY_RAMP_FULL_SECONDS,
    DIFFICULTY_RAMP_GRACE_SECONDS,
    DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX,
    SIM_TICKS_PER_SECOND,
)
from meteorite_dash.difficulty import DifficultyParams, SimulationView


def ramp_speed(tick: int) -> float:
    """Tempofaktor nach `tick` Simulationsschritten: linear von 1.0 auf das Maximum.

    Die ersten `DIFFICULTY_RAMP_GRACE_SECONDS` bleiben bei 1.0, danach steigt
    der Faktor gleichmäßig bis `DIFFICULTY_RAMP_FULL_SECONDS` und bleibt dort.
    """
    seconds = tick / SIM_TICKS_PER_SECOND
    span = DIFFICULTY_RAMP_FULL_SECONDS - DIFFICULTY_RAMP_GRACE_SECONDS
    progress = (seconds - DIFFICULTY_RAMP_GRACE_SECONDS) / span
    progress = max(0.0, min(1.0, progress))
    return 1.0 + (DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX - 1.0) * progress


def ramp_params(tick: int) -> DifficultyParams:
    """Stellgrößen der Rampe: schnellere Welt bei gleichbleibender Dichte."""
    speed = ramp_speed(tick)
    return DifficultyParams(speed_multiplier=speed, spawn_interval_multiplier=1.0 / speed)


class RampDirector:
    """Reine Zeitrampe ohne eigenen Zustand — der Standard des Daily Run.

    Weil er zustandslos ist, taucht er nicht im Simulationshash auf; sein
    Beitrag steckt vollständig in `sim.tick`.
    """

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Hängt nur an der Laufzeit; `rng` bleibt ungenutzt."""
        return ramp_params(sim.tick)
