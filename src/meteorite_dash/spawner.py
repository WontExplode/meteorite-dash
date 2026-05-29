import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from meteorite_dash.entities import Entity

EntityFactory = Callable[[random.Random, tuple[int, int]], Entity]


@dataclass(frozen=True)
class SpawnEntry:
    weight: float
    factory: EntityFactory


class Spawner:
    """Erzeugt Entities timergesteuert über eine gewichtete Tabelle (datengetrieben)."""

    def __init__(
        self,
        table: Sequence[SpawnEntry],
        screen_size: tuple[int, int],
        rng: random.Random,
        interval_range: tuple[float, float],
    ) -> None:
        self._table = list(table)
        self._weights = [entry.weight for entry in self._table]
        self._screen_size = screen_size
        self._rng = rng
        self._interval_range = interval_range
        self._elapsed = 0.0
        self._next_at = self._roll_interval()

    def _roll_interval(self) -> float:
        low, high = self._interval_range
        return self._rng.uniform(low, high)

    def update(self, dt: float) -> list[Entity]:
        self._elapsed += dt
        spawned: list[Entity] = []
        while self._elapsed >= self._next_at:
            self._elapsed -= self._next_at
            entry = self._rng.choices(self._table, weights=self._weights, k=1)[0]
            spawned.append(entry.factory(self._rng, self._screen_size))
            self._next_at = self._roll_interval()
        return spawned
