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
from meteorite_dash.mode_directors import director_for_kind, director_version_for_kind
from meteorite_dash.replay import Replay
from meteorite_dash.simulation import RunConfig, SimEvent, Simulation, Snapshot


@dataclass(frozen=True)
class Trace:
    """Ergebnis eines Headless-Laufs: alle Events plus Endzustand und Hash."""

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
    """Ergebnis von `verify`: Replay und sein Nachspiel-Trace zum Vergleich."""

    replay: Replay
    trace: Trace

    @property
    def version_matches(self) -> bool:
        """True bei passender gemeinsamer Simulations- und Director-Regelversion."""
        return (
            self.replay.sim_version == SIM_VERSION
            and self.replay.director_version == director_version_for_kind(self.replay.director_kind)
        )

    @property
    def ok(self) -> bool:
        """Bit-gleich nachgespielt: gleicher Endzustand, gleicher Hash."""
        return (
            self.version_matches
            and self.trace.final == self.replay.final
            and self.trace.state_hash == self.replay.state_hash
        )


def run_replay(replay: Replay, *, director: Director | None = None) -> Trace:
    """Spielt ein Replay mit seiner aufgezeichneten oder explizit gesetzten Strategie nach."""
    replay_director = director if director is not None else director_for_kind(replay.director_kind)
    return run(replay.config, replay.inputs(), director=replay_director)


def verify(replay: Replay) -> Verification:
    """Spielt `replay` nach und liefert den Vergleich mit dem aufgezeichneten Ende."""
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
