"""Replays (Issue #34): Aufzeichnung, Format, Ablage, Prüfung und Golden-Regression."""

import json
import os
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

import pygame
import pytest

from meteorite_dash.config import REPLAY_BEST_NAME, REPLAY_LAST_NAME, SIM_VERSION
from meteorite_dash.context import GameContext
from meteorite_dash.difficulty import DirectorKind
from meteorite_dash.entities import Meteorite
from meteorite_dash.headless import Trace, format_trace, run_replay, scripted_inputs, verify
from meteorite_dash.inputs import InputFrame
from meteorite_dash.main import main
from meteorite_dash.mode_directors import director_version_for_kind
from meteorite_dash.replay import Recorder, Replay, ReplayStore
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.simulation import RunConfig, Simulation

GOLDEN_DIR = Path(__file__).parent / "replays"
GOLDEN_CONFIG = RunConfig(seed=20260830, ship="Allrounder")
# Eingabe-Seeds mit breiter Event-Abdeckung (Treffer/Zerstörung/Bonus bzw. Munitions-Pickup).
GOLDEN_RUNS = {"golden-a": 71, "golden-b": 7}
GOLDEN_TICKS = 3600  # höchstens 60 Sekunden Spielzeit

CONFIG = RunConfig(seed=4711, ship="Allrounder")


def _record(config: RunConfig, inputs: Iterable[InputFrame]) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config)
    for frame in inputs:
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def _trace_rows(trace: Trace) -> list[dict[str, object]]:
    return [
        {
            "tick": event.snapshot.tick,
            "kind": event.kind.value,
            "value": event.value,
            "hp": event.snapshot.hp,
            "ammo": event.snapshot.ammo,
            "light_years": event.snapshot.light_years,
            "coins": event.snapshot.coins,
            "shield": event.snapshot.shield,
        }
        for event in trace.events
    ]


def _kill(scene: GameScene) -> None:
    rect = scene.sim.player.rect.copy()
    scene.sim.entities.append(Meteorite(rect, 0.0, hp=10, contact_damage=999))
    scene.step(InputFrame.NONE)


# --- Recorder & Format -----------------------------------------------------------------


def test_recorder_run_length_encodes_inputs() -> None:
    recorder = Recorder(CONFIG)
    for frame in (
        (InputFrame.NONE,) * 3 + (InputFrame.FIRE,) * 2 + (InputFrame.UP | InputFrame.FIRE,)
    ):
        recorder.record(frame)
    replay = recorder.finish(Simulation(CONFIG))
    assert replay.frames == ((0, 3), (4, 2), (5, 1))
    assert replay.ticks == 6
    assert list(replay.inputs()) == [InputFrame.NONE] * 3 + [InputFrame.FIRE] * 2 + [
        InputFrame.UP | InputFrame.FIRE
    ]
    assert replay.sim_version == SIM_VERSION
    assert replay.recorded_at  # ISO-Datum gesetzt


def test_replay_json_roundtrip() -> None:
    replay = _record(CONFIG, scripted_inputs(1, 600))
    restored = Replay.from_dict(json.loads(json.dumps(replay.to_dict())))
    assert restored == replay


def test_legacy_replay_defaults_to_constant_director() -> None:
    data = _record(CONFIG, scripted_inputs(1, 60)).to_dict()
    del data["director"]
    del data["director_version"]

    restored = Replay.from_dict(data)

    assert restored is not None
    assert restored.director_kind is DirectorKind.CONSTANT
    assert restored.director_version == director_version_for_kind(DirectorKind.CONSTANT)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: None,
        lambda d: [],
        lambda d: {},
        lambda d: {**d, "format": 99},
        lambda d: {k: v for k, v in d.items() if k != "frames"},
        lambda d: {**d, "frames": [[99, 1]]},  # unbekannte Eingabe-Bits
        lambda d: {**d, "frames": [[0, 0]]},  # leerer Lauf-Abschnitt
        lambda d: {**d, "frames": [[0]]},
        lambda d: {**d, "config": {**d["config"], "ship": "Todesstern"}},
        lambda d: {**d, "config": {**d["config"], "accessories": ["jetpack"]}},
        lambda d: {**d, "config": {**d["config"], "seed": True}},  # bool-als-int
        lambda d: {**d, "state_hash": "nope"},
        lambda d: {**d, "mode": "weekly"},
        lambda d: {**d, "director": "chaos"},
        lambda d: {**d, "director_version": 0},
        lambda d: {**d, "final": {**d["final"], "hp": "voll"}},
    ],
)
def test_replay_from_dict_rejects_garbage(mutate: object) -> None:
    data = _record(CONFIG, scripted_inputs(1, 60)).to_dict()
    assert Replay.from_dict(mutate(data)) is None  # type: ignore[operator]


# --- Ablage ----------------------------------------------------------------------------------


def test_replay_store_roundtrip_and_tolerance(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path / "replays")
    replay = _record(CONFIG, scripted_inputs(2, 300))
    assert store.load("last") is None
    assert store.save("last", replay)
    assert store.load("last") == replay

    (tmp_path / "replays" / "broken.json").write_text("{nope", encoding="utf-8")
    assert store.load("broken") is None
    assert store.all() == [replay]


def test_replay_store_sanitizes_names(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    for name in ("../../etc/passwd", "daily/2026-08-30", "..", "best"):
        path = store.path_for(name)
        assert path.parent == tmp_path
        assert path.suffix == ".json"
    assert store.path_for("daily-2026-08-30").name == "daily-2026-08-30.json"


def test_replay_store_best_for_seed(tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    short = _record(CONFIG, scripted_inputs(1, 120))
    long = _record(CONFIG, scripted_inputs(1, 1200))
    other_seed = _record(replace(CONFIG, seed=1), scripted_inputs(1, 2400))
    old_version = replace(long, sim_version=SIM_VERSION + 1, frames=((0, 6000),))
    store.save("a", short)
    store.save("b", long)
    store.save("c", other_seed)
    store.save("d", old_version)
    assert store.best_for_seed(CONFIG.seed) == long
    assert store.best_for_seed(1) == other_seed
    assert store.best_for_seed(999) is None


# --- Prüfung --------------------------------------------------------------------------------


def test_verify_accepts_recorded_run() -> None:
    replay = _record(CONFIG, scripted_inputs(3, 1500))
    result = verify(replay)
    assert result.ok
    assert result.version_matches
    assert result.trace.final == replay.final


def test_verify_rejects_tampering() -> None:
    replay = _record(CONFIG, scripted_inputs(3, 900))
    better = replace(replay, final=replay.final._replace(light_years=replay.light_years + 1))
    assert not verify(better).ok
    other_inputs = replace(replay, frames=((int(InputFrame.UP), replay.ticks),))
    assert not verify(other_inputs).ok
    old = replace(replay, sim_version=SIM_VERSION + 1)
    assert not verify(old).version_matches
    assert not verify(old).ok
    old_director = replace(replay, director_version=replay.director_version + 1)
    assert not verify(old_director).version_matches
    assert not verify(old_director).ok


def test_format_trace_lists_every_interaction() -> None:
    trace = run_replay(_record(CONFIG, scripted_inputs(3, 900)))
    text = format_trace(trace)
    assert len(text.splitlines()) == len(trace.events) + 1
    assert "fired" in text


def test_verify_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    replay = _record(CONFIG, scripted_inputs(5, 600))
    path = tmp_path / "run.json"
    path.write_text(json.dumps(replay.to_dict()), encoding="utf-8")
    assert main(["--verify", str(path)]) == 0
    assert "PASS" in capsys.readouterr().out

    tampered = replace(replay, state_hash="0" * 64)
    path.write_text(json.dumps(tampered.to_dict()), encoding="utf-8")
    assert main(["--verify", str(path)]) == 1
    assert "FAIL" in capsys.readouterr().out

    path.write_text("kein json", encoding="utf-8")
    assert main(["--verify", str(path)]) == 1
    assert main(["--verify", str(tmp_path / "fehlt.json")]) == 1


# --- Szene ------------------------------------------------------------------------------------


def test_scene_recording_replays_bit_identical(context: GameContext) -> None:
    scene = GameScene(context, seed=CONFIG.seed)
    for frame in scripted_inputs(8, 1200):
        scene.step(frame)
    replay = scene.recorder.finish(scene.sim)
    assert replay.director_kind is DirectorKind.ADAPTIVE
    assert replay.ticks == scene.sim.tick
    assert run_replay(replay).state_hash == scene.sim.state_hash()
    assert verify(replay).ok


def test_scene_stores_last_and_best_on_death(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store

    first = GameScene(context, seed=CONFIG.seed)
    for _ in range(120):
        first.step(InputFrame.NONE)
    _kill(first)
    assert context.state.last_replay is not None
    assert context.state.final_seed == CONFIG.seed
    assert store.load(REPLAY_LAST_NAME) == context.state.last_replay
    assert store.load(REPLAY_BEST_NAME) == context.state.last_replay
    assert context.state.last_replay.ticks == first.sim.tick

    # Frames nach dem Tod werden nicht mehr aufgezeichnet.
    first.step(InputFrame.FIRE)
    assert first.recorder.ticks == first.sim.tick

    worse = GameScene(context, seed=CONFIG.seed)
    _kill(worse)
    assert store.load(REPLAY_LAST_NAME) == context.state.last_replay
    assert store.load(REPLAY_BEST_NAME) != context.state.last_replay

    better = GameScene(context, seed=CONFIG.seed)
    for _ in range(600):
        better.step(InputFrame.NONE)
    _kill(better)
    assert store.load(REPLAY_BEST_NAME) == context.state.last_replay


def test_scene_without_store_keeps_replay_in_memory(context: GameContext) -> None:
    assert context.replays is None
    scene = GameScene(context, seed=1)
    _kill(scene)
    assert context.state.last_replay is not None
    assert context.state.last_replay.config == scene.sim.config


def test_death_screen_shows_seed(context: GameContext) -> None:
    from meteorite_dash.scenes.death import DeathScene

    context.state.final_seed = 42
    DeathScene(context).draw()  # zeichnet ohne Fehler; Text-Inhalt ist nicht pixelprüfbar
    assert pygame.display.get_surface() is context.screen


# --- Golden-Regression ------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(GOLDEN_RUNS))
def test_golden_replay_regression(name: str) -> None:
    """Wörtlicher Beweis: nach jeder Interaktion stimmen Score/HP/Munition mit der
    aufgezeichneten Referenz überein. Neu erzeugen: `UPDATE_GOLDEN=1 uv run pytest
    tests/test_replay.py -k golden` — nur nach bewusster Regeländerung (SIM_VERSION)."""
    replay_path = GOLDEN_DIR / f"{name}.json"
    trace_path = GOLDEN_DIR / f"{name}.trace.json"
    if os.environ.get("UPDATE_GOLDEN"):
        generated = _record(GOLDEN_CONFIG, scripted_inputs(GOLDEN_RUNS[name], GOLDEN_TICKS))
        generated = replace(generated, recorded_at="2026-08-30", label=name)
        GOLDEN_DIR.mkdir(exist_ok=True)
        replay_path.write_text(json.dumps(generated.to_dict()) + "\n", encoding="utf-8")
        rows = _trace_rows(run_replay(generated))
        trace_path.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8")

    replay = Replay.from_dict(json.loads(replay_path.read_text(encoding="utf-8")))
    assert replay is not None, f"{replay_path} fehlt oder ist kaputt"
    assert replay.sim_version == SIM_VERSION, "SIM_VERSION geändert -> Golden neu erzeugen"

    result = verify(replay)
    assert result.ok, "Endzustand/Hash weichen von der Aufzeichnung ab"

    expected = json.loads(trace_path.read_text(encoding="utf-8"))
    actual = _trace_rows(result.trace)
    assert len(actual) == len(expected)
    for row, want in zip(actual, expected, strict=True):
        assert row == want, f"Tick {want['tick']}: {want['kind']} weicht ab"
