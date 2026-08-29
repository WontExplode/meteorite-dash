import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass

type Factory[T] = Callable[[random.Random, tuple[int, int]], T]


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
        screen_size: tuple[int, int],
        rng: random.Random,
        interval_range: tuple[float, float],
    ) -> None:
        self._table = list(table)
        self._weights = [entry.weight for entry in self._table]
        self.screen_size = screen_size
        self._rng = rng
        self._interval_range = interval_range
        self._elapsed = 0.0
        self._next_at = self._roll_interval()

    def set_table(self, table: Sequence[SpawnEntry[T]]) -> None:
        self._table = list(table)
        self._weights = [entry.weight for entry in self._table]

    def _roll_interval(self) -> float:
        low, high = self._interval_range
        return self._rng.uniform(low, high)

    def update(self, dt: float) -> list[T]:
        self._elapsed += dt
        spawned: list[T] = []
        while self._elapsed >= self._next_at:
            self._elapsed -= self._next_at
            entry = self._rng.choices(self._table, weights=self._weights, k=1)[0]
            spawned.append(entry.factory(self._rng, self.screen_size))
            self._next_at = self._roll_interval()
        return spawned
