"""Daily-Bestenliste: Logik über dem ReplayStore, Szene, Menü- und Death-Screen-Wege."""

from dataclasses import replace
from pathlib import Path

import pygame
import pytest

from meteorite_dash.app import App
from meteorite_dash.config import LEADERBOARD_SIZE, MENU_ITEMS, SAVE_DIR_ENV, SIM_VERSION
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.exchange import STATUS_OFFLINE, STATUS_SEARCHING, RunExchange
from meteorite_dash.headless import scripted_inputs
from meteorite_dash.identity import Identity
from meteorite_dash.leaderboard import build_leaderboard
from meteorite_dash.nostr import RelayClient
from meteorite_dash.replay import Recorder, Replay, ReplayStore, RunMode
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.leaderboard import LeaderboardScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.simulation import RunConfig, Simulation

SEED = 579292414
CONFIG = RunConfig(seed=SEED, ship="Allrounder")


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _record(config: RunConfig = CONFIG, ticks: int = 120) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config, mode=RunMode.DAILY, label="2026-08-30")
    for frame in scripted_inputs(1, ticks):
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def _run(
    light_years: float, author: str = "", *, seed: int = SEED, day: str = "2026-08-30"
) -> Replay:
    base = _record(replace(CONFIG, seed=seed))
    return replace(
        base, author=author, recorded_at=day, final=base.final._replace(light_years=light_years)
    )


A = "a" * 64
B = "b" * 64
C = "c" * 64


# --- Logik --------------------------------------------------------------------------------


def test_build_leaderboard_ranks_best_run_per_player() -> None:
    replays = [
        _run(100.0),  # eigener `last`
        _run(300.0),  # eigener `daily-…` (besser)
        _run(500.0, A),
        _run(200.0, B),
        _run(999.0, C, seed=SEED + 1),  # anderer Seed
        replace(_run(800.0, C), sim_version=SIM_VERSION + 1),  # alte Version
    ]
    board = build_leaderboard(replays, SEED)
    assert [(e.rank, e.name, e.light_years) for e in board.entries] == [
        (1, A[:8], 500.0),
        (2, "DU", 300.0),
        (3, B[:8], 200.0),
    ]
    assert board.own is not None
    assert board.own.rank == 2
    assert board.own.ship == "Allrounder"
    assert len(board) == 3
    assert board.top(2) == board.entries[:2]
    assert build_leaderboard([], SEED).own is None


def test_build_leaderboard_ties_prefer_older_run_then_pubkey() -> None:
    replays = [
        _run(100.0, B, day="2026-08-30"),
        _run(100.0, A, day="2026-08-30"),
        _run(100.0, C, day="2026-08-29"),
    ]
    board = build_leaderboard(replays, SEED)
    assert [e.author for e in board.entries] == [C, A, B]


# --- Szene ----------------------------------------------------------------------------------


def test_scene_without_store_draws_empty_list(context: GameContext) -> None:
    scene = LeaderboardScene(context)
    assert scene.seed == daily_seed(today_utc())
    assert scene.label == today_utc().isoformat()
    assert len(scene.board) == 0
    assert scene._own_line() == "DU: NOCH KEIN LAUF ZU DIESEM SEED"
    scene.on_enter()  # kein Exchange -> nichts zu holen
    scene.update(0.016)
    scene.draw()
    scene.handle_event(_keydown(pygame.K_r))  # refresh ohne Exchange
    scene.handle_event(_keydown(pygame.K_ESCAPE))
    assert scene._transition is Transition.MAIN_MENU


def test_scene_shows_top_five_and_own_rank_below(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    for index, author in enumerate(("1" * 64, "2" * 64, "3" * 64, "4" * 64, "5" * 64, "6" * 64)):
        store.save(f"nostr-{index}", _run(1000.0 - index * 10, author))
    store.save("daily-2026-08-30", _run(50.0))

    scene = LeaderboardScene(context, seed=SEED, label="2026-08-30")
    top = scene.board.top(LEADERBOARD_SIZE)
    assert len(top) == LEADERBOARD_SIZE
    assert [entry.rank for entry in top] == [1, 2, 3, 4, 5]
    assert not any(entry.is_own for entry in top)
    assert scene._own_line() == "DU: PLATZ 7 VON 7   000050 LICHTJAHRE"
    scene.draw()

    store.save("daily-2026-08-30", _run(995.0))
    scene.refresh()
    assert scene.board.own is not None
    assert scene.board.own.rank == 2
    assert scene.board.top(LEADERBOARD_SIZE)[1].is_own
    scene.draw()


def test_scene_rebuilds_when_exchange_status_changes(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    exchange = RunExchange(
        Identity.generate(), store, client=RelayClient(["ws://127.0.0.1:1"], timeout=0.5)
    )
    context.exchange = exchange
    scene = LeaderboardScene(context, seed=SEED, label="2026-08-30")
    assert len(scene.board) == 0
    scene.on_enter()
    assert exchange.status in (STATUS_SEARCHING, STATUS_OFFLINE)
    # Während der Suche kommt (von woanders) ein Lauf dazu; erst der Statuswechsel
    # baut die Liste neu.
    store.save("nostr-x", _run(123.0, A))
    exchange.wait_idle(5.0)
    assert exchange.status == STATUS_OFFLINE
    scene.update(0.016)
    assert len(scene.board) == 1
    scene.draw()


# --- Menü, Death-Screen, App --------------------------------------------------------------


def test_menu_offers_leaderboard(context: GameContext) -> None:
    menu = MainMenu(context)
    index = [action for _, action in MENU_ITEMS].index("leaderboard")
    for _ in range(index):
        menu.handle_event(_keydown(pygame.K_DOWN))
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.LEADERBOARD
    menu.draw()


def test_death_screen_tab_opens_leaderboard_after_daily(context: GameContext) -> None:
    state = context.state
    state.final_mode = RunMode.DAILY
    scene = DeathScene(context)
    scene.draw()
    scene.handle_event(_keydown(pygame.K_TAB))
    assert scene._transition is Transition.LEADERBOARD

    scene = DeathScene(context)
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene._transition is Transition.MAIN_MENU

    state.final_mode = RunMode.FREE
    scene = DeathScene(context)
    scene.draw()
    scene.handle_event(_keydown(pygame.K_TAB))
    assert scene._transition is Transition.MAIN_MENU


def test_app_creates_leaderboard_scene(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    app = App()
    try:
        scene = app._create_scene(Transition.LEADERBOARD)
        assert isinstance(scene, LeaderboardScene)
        assert scene.seed == daily_seed(today_utc())
    finally:
        pygame.quit()
