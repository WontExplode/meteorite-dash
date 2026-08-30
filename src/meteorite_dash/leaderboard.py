"""Bestenliste (Issue #34): Top-N-Läufe zu einem Seed aus dem `ReplayStore`.

Reine Logik über die gespeicherten Replays: alle Läufe zum Seed und zur
aktuellen `SIM_VERSION`, ein Eintrag pro Spieler (eigene Läufe haben
`author == ""` und heißen „DU", fremde tragen ihren Pubkey), weiteste zuerst.
Kein Netz — die fremden Dateien legt `RunExchange.import_runs` ab, und die
sind dort schon nachgespielt worden.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from meteorite_dash.config import LEADERBOARD_OWN_LABEL, SIM_VERSION
from meteorite_dash.identity import short_pubkey
from meteorite_dash.replay import Replay


@dataclass(frozen=True)
class LeaderboardEntry:
    rank: int  # 1-basiert
    author: str  # "" = eigener Lauf
    light_years: float
    ship: str
    recorded_at: str

    @property
    def is_own(self) -> bool:
        return self.author == ""

    @property
    def name(self) -> str:
        return LEADERBOARD_OWN_LABEL if self.is_own else short_pubkey(self.author)


@dataclass(frozen=True)
class Leaderboard:
    seed: int
    entries: tuple[LeaderboardEntry, ...]  # vollständig, nach Rang

    def top(self, limit: int) -> tuple[LeaderboardEntry, ...]:
        return self.entries[:limit]

    @property
    def own(self) -> LeaderboardEntry | None:
        return next((entry for entry in self.entries if entry.is_own), None)

    def __len__(self) -> int:
        return len(self.entries)


def build_leaderboard(replays: Iterable[Replay], seed: int) -> Leaderboard:
    """Bester Lauf je Spieler zum Seed, absteigend nach Lichtjahren; Gleichstand
    entscheidet der ältere Lauf, dann der Pubkey (stabil und reproduzierbar)."""
    best: dict[str, Replay] = {}
    for replay in replays:
        if replay.config.seed != seed or replay.sim_version != SIM_VERSION:
            continue
        current = best.get(replay.author)
        if current is None or _ranks_before(replay, current):
            best[replay.author] = replay
    ordered = sorted(best.values(), key=_sort_key)
    entries = tuple(
        LeaderboardEntry(
            rank=index + 1,
            author=replay.author,
            light_years=replay.light_years,
            ship=replay.config.ship,
            recorded_at=replay.recorded_at,
        )
        for index, replay in enumerate(ordered)
    )
    return Leaderboard(seed, entries)


def _sort_key(replay: Replay) -> tuple[float, str, str]:
    return (-replay.light_years, replay.recorded_at, replay.author)


def _ranks_before(candidate: Replay, other: Replay) -> bool:
    return _sort_key(candidate) < _sort_key(other)
