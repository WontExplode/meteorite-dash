"""Replays (Issue #34): Aufzeichnung, JSON-Format und Ablage.

Ein Replay ist `RunConfig` + Eingabefolge (lauflängenkodiert) + Endzustand
(`Snapshot`, `state_hash`). Mehr braucht es nicht: die Simulation ist
deterministisch, also entsteht aus Seed und Eingaben derselbe Lauf — als Ghost,
als Regressionstest oder zur Prüfung eines fremden Laufs (`headless.verify`).

Format: JSON, niemals `pickle`. `Replay.from_dict` parst defensiv wie
`Progress.from_dict`: falsche Typen, unbekannte Schiffe/Zubehör oder kaputte
Frames liefern `None` statt einer Exception.
"""

import functools
import json
import logging
import operator
import os
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from meteorite_dash.config import REPLAY_DIR_NAME, REPLAY_FORMAT_VERSION, SIM_VERSION
from meteorite_dash.inputs import InputFrame
from meteorite_dash.persistence import default_save_dir
from meteorite_dash.simulation import RunConfig, Simulation, Snapshot

log = logging.getLogger(__name__)

_ALL_INPUTS = functools.reduce(operator.or_, InputFrame)
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")
_HASH = re.compile(r"^[0-9a-f]{64}$")

Frames = tuple[tuple[int, int], ...]  # (Maske, Anzahl Ticks)


class RunMode(Enum):
    FREE = "free"  # zufälliger Seed, Rekord in `best`
    DAILY = "daily"  # Tages-Seed, Rekord in `daily-<datum>`


@dataclass(frozen=True)
class Replay:
    config: RunConfig
    frames: Frames
    final: Snapshot
    state_hash: str
    sim_version: int = SIM_VERSION
    recorded_at: str = ""  # ISO-Datum (UTC)
    mode: RunMode = RunMode.FREE
    label: str = ""  # z. B. Daily-Datum
    # Pubkey des Spielers bei importierten Community-Läufen, sonst leer (eigener Lauf).
    author: str = ""

    @property
    def ticks(self) -> int:
        return sum(count for _, count in self.frames)

    @property
    def light_years(self) -> float:
        return self.final.light_years

    def inputs(self) -> Iterator[InputFrame]:
        for mask, count in self.frames:
            frame = InputFrame(mask)
            for _ in range(count):
                yield frame

    # --- Serialisierung ------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "format": REPLAY_FORMAT_VERSION,
            "sim_version": self.sim_version,
            "recorded_at": self.recorded_at,
            "mode": self.mode.value,
            "label": self.label,
            "author": self.author,
            "config": {
                "seed": self.config.seed,
                "ship": self.config.ship,
                "accessories": list(self.config.accessories),
            },
            "frames": [[mask, count] for mask, count in self.frames],
            "final": self.final._asdict(),
            "state_hash": self.state_hash,
        }

    @classmethod
    def from_dict(cls, data: object) -> "Replay | None":
        if not isinstance(data, dict):
            return None
        try:
            if _as_int(data["format"]) != REPLAY_FORMAT_VERSION:
                return None
            raw_config = data["config"]
            if not isinstance(raw_config, dict):
                return None
            config = RunConfig(
                _as_int(raw_config["seed"]),
                _as_str(raw_config["ship"]),
                tuple(_as_str(acc) for acc in _as_list(raw_config.get("accessories", []))),
            )
            frames = tuple(_as_frame(item) for item in _as_list(data["frames"]))
            raw_final = data["final"]
            if not isinstance(raw_final, dict):
                return None
            final = Snapshot(
                tick=_as_int(raw_final["tick"]),
                hp=_as_int(raw_final["hp"]),
                ammo=_as_int(raw_final["ammo"]),
                light_years=_as_float(raw_final["light_years"]),
                coins=_as_int(raw_final["coins"]),
                shield=_as_int(raw_final["shield"]),
            )
            state_hash = _as_str(data["state_hash"])
            if not _HASH.match(state_hash):
                return None
            return cls(
                config=config,
                frames=frames,
                final=final,
                state_hash=state_hash,
                sim_version=_as_int(data.get("sim_version", 0)),
                recorded_at=_as_str(data.get("recorded_at", "")),
                mode=RunMode(_as_str(data.get("mode", RunMode.FREE.value))),
                label=_as_str(data.get("label", "")),
                author=_as_str(data.get("author", "")),
            )
        except (KeyError, TypeError, ValueError):
            return None


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"int erwartet, {type(value).__name__} bekommen")
    return value


def _as_float(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"float erwartet, {type(value).__name__} bekommen")
    return float(value)


def _as_str(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"str erwartet, {type(value).__name__} bekommen")
    return value


def _as_list(value: object) -> list[object]:
    if not isinstance(value, list):
        raise TypeError(f"list erwartet, {type(value).__name__} bekommen")
    return value


def _as_frame(value: object) -> tuple[int, int]:
    pair = _as_list(value)
    if len(pair) != 2:
        raise ValueError("Frame braucht [Maske, Anzahl]")
    mask, count = _as_int(pair[0]), _as_int(pair[1])
    if count <= 0 or mask & ~int(_ALL_INPUTS):
        raise ValueError("ungültiger Frame")
    return mask, count


# --- Aufzeichnung --------------------------------------------------------------


@dataclass
class Recorder:
    """Sammelt die Eingaben eines Laufs lauflängenkodiert."""

    config: RunConfig
    mode: RunMode = RunMode.FREE
    label: str = ""
    _frames: list[list[int]] = field(default_factory=list)

    @property
    def ticks(self) -> int:
        return sum(count for _, count in self._frames)

    def record(self, inputs: InputFrame) -> None:
        mask = int(inputs)
        if self._frames and self._frames[-1][0] == mask:
            self._frames[-1][1] += 1
        else:
            self._frames.append([mask, 1])

    def finish(self, sim: Simulation) -> Replay:
        return Replay(
            config=self.config,
            frames=tuple((mask, count) for mask, count in self._frames),
            final=sim.snapshot(),
            state_hash=sim.state_hash(),
            sim_version=SIM_VERSION,
            recorded_at=datetime.now(UTC).date().isoformat(),
            mode=self.mode,
            label=self.label,
        )


# --- Ablage -----------------------------------------------------------------------


def default_replay_dir() -> Path:
    return default_save_dir() / REPLAY_DIR_NAME


class ReplayStore:
    """Replays als `<name>.json` in einem Ordner; Namen werden bereinigt."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def path_for(self, name: str) -> Path:
        safe = _SAFE_NAME.sub("_", name).strip("_") or "replay"
        return self.directory / f"{safe}.json"

    def load(self, name: str) -> Replay | None:
        return self._read(self.path_for(name))

    def save(self, name: str, replay: Replay) -> bool:
        path = self.path_for(name)
        payload = json.dumps(replay.to_dict(), indent=2)
        tmp_path = path.with_name(path.name + ".tmp")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp_path.write_text(payload, encoding="utf-8")
            os.replace(tmp_path, path)
        except OSError as exc:
            log.warning("Replay %s nicht schreibbar: %s", path, exc)
            return False
        return True

    def all(self) -> list[Replay]:
        try:
            paths = sorted(self.directory.glob("*.json"))
        except OSError:
            return []
        return [replay for replay in (self._read(path) for path in paths) if replay is not None]

    def best_for_seed(self, seed: int, *, sim_version: int = SIM_VERSION) -> Replay | None:
        """Weitester gespeicherter Lauf mit diesem Seed — nur aus derselben Sim-Version."""
        candidates = [
            replay
            for replay in self.all()
            if replay.config.seed == seed and replay.sim_version == sim_version
        ]
        return max(candidates, key=lambda replay: replay.light_years, default=None)

    def _read(self, path: Path) -> Replay | None:
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except (OSError, UnicodeDecodeError) as exc:
            log.warning("Replay %s nicht lesbar: %s", path, exc)
            return None
        try:
            data: object = json.loads(raw)
        except ValueError as exc:
            log.warning("Replay %s ist kein gültiges JSON: %s", path, exc)
            return None
        replay = Replay.from_dict(data)
        if replay is None:
            log.warning("Replay %s hat ein unbekanntes Format", path)
        return replay
