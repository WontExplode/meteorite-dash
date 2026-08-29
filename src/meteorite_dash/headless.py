"""Headless-Läufe der Simulation (Issue #34): Regressionstests und Replay-Prüfung.

Kein Fenster, kein Audio, keine Wandzeit — nur `Simulation.step` in einer
Schleife. Das Ergebnis (`Trace`) ist der wörtliche Beweis: nach jeder
Interaktion stehen Score, HP und Munition im Event-Snapshot. `verify` spielt
ein `Replay` nach und vergleicht Endzustand und Hash — dieselbe Prüfung, die
später ein Server für eingereichte Läufe fahren kann.
"""

import random
from collections.abc import Iterable, Iterator
from dataclasses import dataclass

from meteorite_dash.config import SIM_VERSION
from meteorite_dash.difficulty import Director
from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Replay
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


# --- Replays prüfen ------------------------------------------------------------


@dataclass(frozen=True)
class Verification:
    replay: Replay
    trace: Trace

    @property
    def version_matches(self) -> bool:
        return self.replay.sim_version == SIM_VERSION

    @property
    def ok(self) -> bool:
        """Bit-gleich nachgespielt: gleicher Endzustand, gleicher Hash."""
        return (
            self.version_matches
            and self.trace.final == self.replay.final
            and self.trace.state_hash == self.replay.state_hash
        )


def run_replay(replay: Replay, *, director: Director | None = None) -> Trace:
    return run(replay.config, replay.inputs(), director=director)


def verify(replay: Replay) -> Verification:
    return Verification(replay, run_replay(replay))


def format_trace(trace: Trace) -> str:
    """Eine Zeile pro Interaktion: Tick, Art, Wert, dann HP/Munition/Lichtjahre/Münzen."""
    lines = [f"{'TICK':>6}  {'EVENT':<12}{'VAL':>4}  {'HP':>4} {'AMMO':>4} {'LY':>9} {'COINS':>5}"]
    for event in trace.events:
        snap = event.snapshot
        lines.append(
            f"{snap.tick:>6}  {event.kind.value:<12}{event.value:>4}  "
            f"{snap.hp:>4} {snap.ammo:>4} {snap.light_years:>9.2f} {snap.coins:>5}"
        )
    return "\n".join(lines)
