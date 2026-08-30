"""Ghost (Issue #34): ein aufgezeichneter Lauf, der im Gleichschritt mitfliegt.

Der Ghost ist keine Positionsliste, sondern eine zweite `Simulation`, die die
Eingaben des Replays Tick für Tick nachspielt. Das kostet fast nichts und hat
zwei Vorteile: die Datei bleibt winzig, und jeder Ghost-Lauf prüft nebenbei,
dass die Simulation noch bit-gleich reproduziert (`consistent`). Gezeichnet
wird nur das Schiff des Ghosts — seine Welt (Spawns nach der ersten
Abweichung, Treffer, Münzen) ist eine andere als die des Spielers.
"""

from collections.abc import Iterator

import pygame

from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Replay
from meteorite_dash.simulation import Simulation


class Ghost:
    """Zweite `Simulation`, die ein Replay Tick für Tick nachspielt.

    `finished` wird True, wenn die Eingaben aufgebraucht sind oder der Ghost
    stirbt; erst dann steht `consistent` fest.
    """

    def __init__(self, replay: Replay) -> None:
        self.replay = replay
        self.sim = Simulation(replay.config)
        self._inputs: Iterator[InputFrame] = replay.inputs()
        self.finished = False
        # Erst nach dem letzten Tick bekannt: Endzustand == Aufzeichnung?
        self.consistent: bool | None = None

    @property
    def rect(self) -> pygame.Rect:
        """Hitbox des Ghost-Schiffs im Referenzraum."""
        return self.sim.player.rect

    @property
    def light_years(self) -> float:
        """Aktuelle Lichtjahre des Ghosts."""
        return self.sim.light_years

    def delta(self, light_years: float) -> float:
        """Vorsprung des Spielers (positiv = vor dem Ghost)."""
        return light_years - self.sim.light_years

    def step(self) -> None:
        """Rückt den Ghost um einen Tick vor; nach dem Ende ein No-op."""
        if self.finished:
            return
        frame = next(self._inputs, None)
        if frame is None:
            self._finish()
            return
        self.sim.step(frame)
        if self.sim.is_over:
            self._finish()

    def _finish(self) -> None:
        """Beendet den Ghost und prüft Snapshot + Hash gegen die Aufzeichnung."""
        self.finished = True
        self.consistent = (
            self.sim.snapshot() == self.replay.final
            and self.sim.state_hash() == self.replay.state_hash
        )
