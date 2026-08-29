import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from meteorite_dash.config import SPAWN_MAX_ATTEMPTS

# Fabrik: (RNG, Spawn-Fläche im Referenzraum) -> Objekt
type Factory[T] = Callable[[random.Random, tuple[int, int]], T]
type Acceptor[T] = Callable[[T], bool]


@dataclass(frozen=True)
class SpawnEntry[T]:
    weight: float
    factory: Factory[T]


class Spawner[T]:
    """Erzeugt Objekte timergesteuert über eine gewichtete Tabelle (datengetrieben).

    Generisch über den Spawn-Typ: einzelne Gegner-`Entity`s ebenso wie ganze
    Münz-Formationen. Jede Instanz hat ihren eigenen Timer, damit sich die
    Tabellen nicht gegenseitig verwässern.
    """

    def __init__(
        self,
        table: Sequence[SpawnEntry[T]],
        area: tuple[int, int],
        rng: random.Random,
        interval_range: tuple[float, float],
        *,
        max_attempts: int = SPAWN_MAX_ATTEMPTS,
    ) -> None:
        self._table = list(table)
        self._weights = [entry.weight for entry in self._table]
        self.area = area
        self._rng = rng
        self._interval_range = interval_range
        self._max_attempts = max_attempts
        self._elapsed = 0.0
        self._next_at = self._roll_interval()

    def set_table(self, table: Sequence[SpawnEntry[T]]) -> None:
        self._table = list(table)
        self._weights = [entry.weight for entry in self._table]

    def _roll_interval(self) -> float:
        low, high = self._interval_range
        return self._rng.uniform(low, high)

    def _roll(self, accept: Acceptor[T] | None) -> T | None:
        """Zieht Kandidaten, bis `accept` einen annimmt; None nach `max_attempts` Absagen."""
        for _ in range(self._max_attempts):
            entry = self._rng.choices(self._table, weights=self._weights, k=1)[0]
            candidate = entry.factory(self._rng, self.area)
            if accept is None or accept(candidate):
                return candidate
        return None

    def update(
        self,
        dt: float,
        accept: Acceptor[T] | None = None,
        *,
        interval_scale: float = 1.0,
    ) -> list[T]:
        """Spawnt fällige Objekte; `accept` kann Kandidaten ablehnen (z. B. Überlappung).

        `interval_scale` streckt (> 1) oder staucht (< 1) das gewürfelte Intervall —
        die Stellgröße des Schwierigkeits-Directors.
        """
        self._elapsed += dt
        spawned: list[T] = []
        due = self._next_at * interval_scale
        while self._elapsed >= due:
            self._elapsed -= due
            candidate = self._roll(accept)
            if candidate is not None:
                spawned.append(candidate)
            self._next_at = self._roll_interval()
            due = self._next_at * interval_scale
        return spawned

    def state_key(self) -> tuple[object, ...]:
        """Timer plus kompletter RNG-Zustand — der Stream gehört zum Spielzustand."""
        return (self._elapsed.hex(), self._next_at.hex(), self._rng.getstate())
