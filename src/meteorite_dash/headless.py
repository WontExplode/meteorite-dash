"""Headless-Läufe der Simulation (Issue #34): Regressionstests und Replay-Prüfung.

Kein Fenster, kein Audio, keine Wandzeit — nur `Simulation.step` in einer
Schleife. Das Ergebnis (`Trace`) ist der wörtliche Beweis: nach jeder
Interaktion stehen Score, HP und Munition im Event-Snapshot.
"""

import random
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from meteorite_dash.difficulty import Director
from meteorite_dash.inputs import InputFrame
from meteorite_dash.simulation import RunConfig, SimEvent, Simulation, Snapshot


@dataclass(frozen=True)
class Trace:
    events: tuple[SimEvent, ...]
    final: Snapshot
    state_hash: str


def run(
    config: RunConfig,
    inputs: Iterable[InputFrame],
    *,
    max_ticks: int | None = None,
    director: Director | None = None,
) -> Trace:
    """Spielt `inputs` Tick für Tick ab; endet beim Tod, am Ende der Eingaben
    oder nach `max_ticks`."""
    sim = Simulation(config, director=director)
    events: list[SimEvent] = []
    for frame in inputs:
        if sim.is_over or (max_ticks is not None and sim.tick >= max_ticks):
            break
        events.extend(sim.step(frame))
    return Trace(tuple(events), sim.snapshot(), sim.state_hash())


def scripted_inputs(seed: int, ticks: int) -> Iterator[InputFrame]:
    """Reproduzierbare Pseudo-Eingaben mit menschlichen Haltezeiten (für Tests)."""
    rng = random.Random(f"inputs:{seed}")
    produced = 0
    while produced < ticks:
        frame = InputFrame.NONE
        roll = rng.random()
        if roll < 0.35:
            frame |= InputFrame.UP
        elif roll < 0.7:
            frame |= InputFrame.DOWN
        if rng.random() < 0.3:
            frame |= InputFrame.FIRE
        for _ in range(min(rng.randint(5, 40), ticks - produced)):
            yield frame
            produced += 1
