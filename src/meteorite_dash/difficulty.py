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
    RAMP = "ramp"


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
    def light_years(self) -> float:
        """Zurückgelegte Lichtjahre."""


class Director(Protocol):
    """Protokoll für Schwierigkeits-Directors (Rampe #32, adaptiv #33)."""

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Wird jeden Tick gerufen; `rng` ist der eigene Stream `<seed>:director`."""


@runtime_checkable
class StatefulDirector(Protocol):
    """Optionaler vollständiger Zustand eines Directors für Replay-Hashes."""

    def state_key(self) -> tuple[object, ...]: ...


class ConstantDirector:
    """Director ohne Rampe und ohne Adaption — feste Stellgrößen für Tests und
    für ältere Replays, die noch unter dieser Strategie aufgezeichnet wurden."""

    def __init__(self, params: DifficultyParams | None = None) -> None:
        self._params = params or DifficultyParams()

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Liefert immer dieselben Stellgrößen; `sim` und `rng` bleiben ungenutzt."""
        return self._params


class CompositeDirector:
    """Multipliziert die Stellgrößen mehrerer Directors und deckelt das Ergebnis.

    So trägt die Zeitrampe das langfristige Tempo, während der adaptive Director
    nur noch um sie herum moduliert. Der Deckel gilt für das Produkt, nicht für
    die einzelnen Teile — sonst könnten zwei je erlaubte Faktoren gemeinsam
    darüber hinausschießen.
    """

    def __init__(
        self,
        *directors: Director,
        speed_cap: float,
        interval_floor: float,
    ) -> None:
        if not directors:
            raise ValueError("CompositeDirector braucht mindestens einen Director")
        if speed_cap < 1.0 or not 0.0 < interval_floor <= 1.0:
            raise ValueError("Unplausibler Deckel für den CompositeDirector")
        self.directors = directors
        self._speed_cap = speed_cap
        self._interval_floor = interval_floor

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Fragt jeden Teil-Director und verrechnet die Stellgrößen multiplikativ."""
        speed = 1.0
        interval = 1.0
        for director in self.directors:
            part = director.params(sim, rng)
            speed *= part.speed_multiplier
            interval *= part.spawn_interval_multiplier
        return DifficultyParams(
            speed_multiplier=min(speed, self._speed_cap),
            spawn_interval_multiplier=max(interval, self._interval_floor),
        )

    def state_key(self) -> tuple[object, ...]:
        """Zustand der zustandsbehafteten Teile; zustandslose tragen nichts bei."""
        return tuple(
            director.state_key()
            for director in self.directors
            if isinstance(director, StatefulDirector)
        )
