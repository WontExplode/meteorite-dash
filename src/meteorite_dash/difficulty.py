"""Schwierigkeits-Vertrag zwischen Simulation und Director (Issues #32/#33/#34).

Der Director selbst ist nicht Teil dieses Moduls — nur die Schnittstelle, an
die er sich halten muss, damit Replays bit-gleich bleiben:

- Seine Entscheidungen hängen nur von Sim-Zustand, eigenem reproduzierbarem
  Zustand und eigenem RNG-Stream ab. Er liest nie Wandzeit, FPS, Fenstergröße
  oder ungeseedeten Zufall.
- Er wird **jeden Tick** aus `Simulation.step` gefragt und liefert
  `DifficultyParams`; Kadenz ("nur alle N Ticks neu bewerten") zählt er selbst
  über `sim.tick`, nie über Sekunden Wandzeit.
- Beinahe-Kollisionen, Munition, HP usw. liest er aus `SimulationView` — alles
  Zustand, der bei gleichen Eingaben identisch entsteht.
- Ein zustandsbehafteter Director implementiert zusätzlich `StatefulDirector`,
  damit sein Zustand in den Simulationshash aufgenommen werden kann.
- Regeländerungen am Director sind Sim-Regeländerungen: `SIM_VERSION` erhöhen.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable

from meteorite_dash.entities import Entity
from meteorite_dash.player import Player
from meteorite_dash.weapons import WeaponLoadout


class DirectorKind(Enum):
    """Stabile Kennung einer Schwierigkeitsstrategie im Replay-Format."""

    CONSTANT = "constant"
    ADAPTIVE = "adaptive"


@dataclass(frozen=True)
class DifficultyParams:
    """Stellgrößen, die die Simulation pro Tick anwendet."""

    # Faktor auf die horizontale Geschwindigkeit aller Gefahren, Pickups und Münzen.
    speed_multiplier: float = 1.0
    # Faktor auf die Spawn-Intervalle (< 1.0 = dichter).
    spawn_interval_multiplier: float = 1.0

    def __post_init__(self) -> None:
        if self.speed_multiplier <= 0 or self.spawn_interval_multiplier <= 0:
            raise ValueError("Schwierigkeits-Faktoren müssen > 0 sein")


class SimulationView(Protocol):
    """Lesezugriff des Directors auf die Simulation (Attribute, kein Verhalten)."""

    tick: int
    player: Player
    loadout: WeaponLoadout
    entities: list[Entity]
    coins_collected: int

    @property
    def light_years(self) -> float: ...


class Director(Protocol):
    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Wird jeden Tick gerufen; `rng` ist der eigene Stream `<seed>:director`."""


@runtime_checkable
class StatefulDirector(Protocol):
    """Optionaler vollständiger Zustand eines Directors für Replay-Hashes."""

    def state_key(self) -> tuple[object, ...]: ...


class ConstantDirector:
    """Standard ohne Rampe/Adaption — der Platzhalter, bis Issue #32/#33 landet."""

    def __init__(self, params: DifficultyParams | None = None) -> None:
        self._params = params or DifficultyParams()

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        return self._params
