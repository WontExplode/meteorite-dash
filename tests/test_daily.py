"""Daily Run (Issue #34): Tages-Seed, Menü, Rekord des Tages und Death-Screen."""

import json
from datetime import date
from pathlib import Path

import pygame
import pytest

from meteorite_dash.app import App
from meteorite_dash.config import (
    DAILY_REPLAY_PREFIX,
    MENU_ITEMS,
    REPLAY_BEST_NAME,
    REPLAY_LAST_NAME,
    SAVE_DIR_ENV,
    SEED_BITS,
)
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_replay_name, daily_seed, today_utc
from meteorite_dash.difficulty import ConstantDirector, DifficultyParams, DirectorKind
from meteorite_dash.entities import Meteorite
from meteorite_dash.inputs import InputFrame
from meteorite_dash.replay import Replay, ReplayStore, RunMode
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu

DAY = date(2026, 8, 30)
LABEL = DAY.isoformat()


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _daily_scene(context: GameContext) -> GameScene:
    return GameScene(context, seed=daily_seed(DAY), mode=RunMode.DAILY, label=LABEL)


def _run_and_die(scene: GameScene, ticks: int) -> None:
    for _ in range(ticks):
        scene.step(InputFrame.NONE)
    scene.sim.entities.append(
        Meteorite(scene.sim.player.rect.copy(), 0.0, hp=10, contact_damage=999)
    )
    scene.step(InputFrame.NONE)


# --- Seed --------------------------------------------------------------------------------


def test_daily_seed_is_stable_across_runs_and_machines() -> None:
    # Festgenagelt: ändert sich dieser Wert, bekommen Spieler verschiedene Tage.
    assert daily_seed(date(2026, 8, 30)) == 579292414
    assert daily_seed(date(2026, 8, 31)) == 1484649728
    assert daily_seed(date(2000, 1, 1)) == 149435307
    assert 0 <= daily_seed(today_utc()) < (1 << SEED_BITS)


def test_daily_replay_name() -> None:
    assert daily_replay_name(DAY) == f"{DAILY_REPLAY_PREFIX}2026-08-30"


# --- Menü & App ------------------------------------------------------------------------------


def test_menu_offers_daily_run(context: GameContext) -> None:
    menu = MainMenu(context)
    index = [action for _, action in MENU_ITEMS].index("daily")
    for _ in range(index):
        menu.handle_event(_keydown(pygame.K_DOWN))
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.START_DAILY
    menu.draw()


def test_app_starts_daily_scene_with_todays_seed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    app = App()
    try:
        scene = app._create_scene(Transition.START_DAILY)
        assert isinstance(scene, GameScene)
        assert scene.mode is RunMode.DAILY
        assert scene.label == today_utc().isoformat()
        assert scene.seed == daily_seed(today_utc())
        assert scene.recorder.mode is RunMode.DAILY
        assert scene.recorder.director_kind is DirectorKind.CONSTANT
        assert isinstance(scene.sim.director, ConstantDirector)
        scene.step(InputFrame.NONE)
        assert scene.sim.difficulty == DifficultyParams()
        free = app._create_scene(Transition.START_GAME)
        assert isinstance(free, GameScene)
        assert free.mode is RunMode.FREE
        assert free.recorder.director_kind is DirectorKind.ADAPTIVE
    finally:
        pygame.quit()


# --- Rekord des Tages ----------------------------------------------------------------------------


def test_daily_death_stores_best_of_day(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    name = daily_replay_name(DAY)

    first = _daily_scene(context)
    assert first.ghost is None
    assert first.record_name() == name
    _run_and_die(first, 120)
    state = context.state
    assert state.final_mode is RunMode.DAILY
    assert state.final_label == LABEL
    assert state.final_record_light_years is None
    assert store.load(name) == state.last_replay
    assert store.load(REPLAY_LAST_NAME) == state.last_replay
    assert store.load(REPLAY_BEST_NAME) is None
    assert state.last_replay is not None
    assert state.last_replay.mode is RunMode.DAILY
    assert state.last_replay.label == LABEL
    record = state.last_replay

    worse = _daily_scene(context)
    assert worse.ghost is not None
    assert worse.ghost.replay == record
    _run_and_die(worse, 10)
    assert state.final_record_light_years == record.light_years
    assert store.load(name) == record

    better = _daily_scene(context)
    _run_and_die(better, 600)
    assert store.load(name) == state.last_replay
    assert state.last_replay != record


def test_free_run_keeps_best_separate_from_daily(context: GameContext, tmp_path: Path) -> None:
    context.replays = ReplayStore(tmp_path)
    free = GameScene(context, seed=daily_seed(DAY))
    assert free.record_name() == REPLAY_BEST_NAME
    _run_and_die(free, 30)
    assert context.replays.load(REPLAY_BEST_NAME) is not None
    assert context.replays.load(daily_replay_name(DAY)) is None


def test_replay_mode_survives_json() -> None:
    context_free = Replay.from_dict(json.loads(json.dumps(_replay_dict(mode="daily", label=LABEL))))
    assert context_free is not None
    assert context_free.mode is RunMode.DAILY
    assert context_free.label == LABEL
    assert Replay.from_dict(_replay_dict(mode="weekly")) is None


def _replay_dict(*, mode: str, label: str = "") -> dict[str, object]:
    return {
        "format": 1,
        "sim_version": 1,
        "recorded_at": "2026-08-30",
        "mode": mode,
        "label": label,
        "config": {"seed": 1, "ship": "Allrounder", "accessories": []},
        "frames": [[0, 3]],
        "final": {"tick": 3, "hp": 100, "ammo": 7, "light_years": 0.6, "coins": 0, "shield": 0},
        "state_hash": "0" * 64,
    }


# --- Death-Screen ---------------------------------------------------------------------------------


def test_death_screen_record_lines(context: GameContext) -> None:
    state = context.state
    scene = DeathScene(context)

    state.final_record_light_years = None
    assert scene._record_line()[0] == ""

    state.final_light_years = 1000.0
    state.final_record_light_years = 932.0
    assert scene._record_line()[0] == "NEUER REKORD (VORHER 000932)"

    state.final_light_years = 630.4
    assert scene._record_line()[0] == "REKORD 000932 (-302)"

    state.final_mode = RunMode.DAILY
    state.final_label = LABEL
    scene.draw()  # Daily-Zeile + Rekord-Zeile zeichnen ohne Fehler
