"""Lauf per Code weitergeben: Share-Event, Suche, Code-Eingabe, Rennen und Zuschauen."""

import json
import threading
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pygame
import pytest
from fake_relay import FakeRelay

from meteorite_dash.config import (
    IDENTITY_FILENAME,
    MENU_ITEMS,
    NOSTR_RUN_KIND,
    NOSTR_SHARE_EXPIRY_SECONDS,
    SAVE_DIR_ENV,
    SIM_DT,
    SIM_VERSION,
)
from meteorite_dash.context import GameContext
from meteorite_dash.exchange import (
    LOOKUP_INVALID,
    LOOKUP_NOT_FOUND,
    LOOKUP_OFFLINE,
    LOOKUP_SEARCHING,
    LOOKUP_VERSION,
    RunExchange,
    describe_run,
    share_name,
)
from meteorite_dash.headless import scripted_inputs
from meteorite_dash.identity import Identity, IdentityStore
from meteorite_dash.inputs import InputFrame
from meteorite_dash.nostr import RelayClient, build_share_event, parse_run_event, share_tag
from meteorite_dash.phrase import phrase_for_hash
from meteorite_dash.replay import Recorder, Replay, ReplayStore, RunMode
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.code_entry import HINT_FORMAT, OFFLINE_LOCAL_ONLY, CodeEntryScene
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.simulation import RunConfig, Simulation

GOLDEN_A = Path(__file__).parent / "replays" / "golden-a.json"
CONFIG = RunConfig(seed=4711, ship="Allrounder")


def _keydown(key: int, unicode: str = "") -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key, unicode=unicode)


def _type(scene: CodeEntryScene, text: str) -> None:
    for char in text:
        scene.handle_event(_keydown(pygame.K_a, char))


def _record(config: RunConfig = CONFIG, input_seed: int = 3, ticks: int = 600) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config, mode=RunMode.FREE)
    for frame in scripted_inputs(input_seed, ticks):
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def _golden_a() -> Replay:
    replay = Replay.from_dict(json.loads(GOLDEN_A.read_text(encoding="utf-8")))
    assert replay is not None
    return replay


@pytest.fixture
def relay() -> Iterator[FakeRelay]:
    fake = FakeRelay().start()
    yield fake
    fake.stop()


def _exchange(relay: FakeRelay, directory: Path, timeout: float = 5.0) -> RunExchange:
    identity = IdentityStore(directory / IDENTITY_FILENAME).load_or_create()
    store = ReplayStore(directory / "replays")
    return RunExchange(identity, store, client=RelayClient([relay.url], timeout=timeout))


def _wait_lookup(scene: CodeEntryScene, exchange: RunExchange) -> None:
    exchange.wait_idle(10.0)
    scene.update(0.016)


# --- Event -----------------------------------------------------------------------------


def test_share_event_is_addressed_by_phrase_and_expires() -> None:
    identity = Identity.generate()
    run = _record()
    phrase = phrase_for_hash(run.state_hash)
    event = build_share_event(identity, run, created_at=1_700_000_000)
    assert event["kind"] == NOSTR_RUN_KIND
    tags = event["tags"]
    assert isinstance(tags, list)
    assert ["d", share_tag(phrase)] in tags
    assert ["expiration", str(1_700_000_000 + NOSTR_SHARE_EXPIRY_SECONDS)] in tags
    parsed = parse_run_event(event)
    assert parsed is not None
    assert parsed.replay == run

    # Fremder Lauf unter falscher Adresse (d-Tag passt nicht zum Hash) wird verworfen.
    wrong = {**event, "tags": [["d", share_tag("abend abend abend")]]}
    assert parse_run_event(wrong) is None  # ID passt nicht mehr — und der Tag auch nicht


# --- Exchange --------------------------------------------------------------------------


def test_share_and_lookup_roundtrip(relay: FakeRelay, tmp_path: Path) -> None:
    alice = _exchange(relay, tmp_path / "alice")
    bob = _exchange(relay, tmp_path / "bob")
    run = _record(ticks=900)
    phrase, accepted = alice.share_now(run)
    assert accepted == 1
    assert phrase == phrase_for_hash(run.state_hash)
    assert alice.share_status == f"CODE: {phrase} — GETEILT (1/1 RELAYS)"

    lookup = bob.lookup_now(phrase.upper())
    assert lookup.done
    assert lookup.replay is not None
    assert replace(lookup.replay, author="") == run
    assert lookup.replay.author == alice.identity.pubkey
    assert lookup.message == describe_run(lookup.replay)
    assert bob.store.load(share_name(phrase)) == lookup.replay

    # Zweite Suche kommt aus dem Store — auch ohne Relay.
    offline = RunExchange(
        bob.identity, bob.store, client=RelayClient(["ws://127.0.0.1:1"], timeout=0.5)
    )
    assert offline.lookup_now(phrase).replay == lookup.replay
    assert offline.lookup_now("abend abend abend").message == LOOKUP_OFFLINE
    assert bob.lookup_now("abend abend abend").message == LOOKUP_NOT_FOUND


def test_lookup_rejects_tampered_and_old_runs(relay: FakeRelay, tmp_path: Path) -> None:
    cheater = _exchange(relay, tmp_path / "cheater")
    honest = _exchange(relay, tmp_path / "honest")
    run = _record(ticks=600)
    faked = replace(run, final=run.final._replace(light_years=run.light_years + 500))
    phrase, _ = cheater.share_now(faked)
    result = honest.lookup_now(phrase)
    assert result.replay is None
    assert result.message == LOOKUP_INVALID
    assert honest.store.all() == []

    old = replace(_record(input_seed=9, ticks=300), sim_version=SIM_VERSION + 1)
    phrase_old, _ = cheater.share_now(old)
    assert honest.lookup_now(phrase_old).message == LOOKUP_VERSION


def test_background_share_and_lookup(relay: FakeRelay, tmp_path: Path) -> None:
    alice = _exchange(relay, tmp_path / "alice")
    bob = _exchange(relay, tmp_path / "bob")
    run = _record(ticks=300)
    phrase = alice.share(run)
    assert alice.share_status.startswith(f"CODE: {phrase} — TEILE")
    alice.wait_idle(10.0)
    assert "GETEILT" in alice.share_status

    bob.start_lookup(phrase)
    assert bob.lookup is not None
    assert bob.lookup.message == LOOKUP_SEARCHING
    bob.wait_idle(10.0)
    assert bob.lookup.done
    assert bob.lookup.replay is not None


def test_share_does_not_restart_for_same_run_while_in_flight(
    relay: FakeRelay, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mehrfaches `C` auf dem Death-Screen (`DeathScene.share`) darf keinen zweiten
    Hintergrund-Thread für denselben Lauf anstoßen, solange der erste noch läuft."""
    exchange = _exchange(relay, tmp_path)
    run = _record(ticks=300)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def slow_share_now(replay: Replay) -> tuple[str, int]:
        nonlocal calls
        calls += 1
        started.set()
        release.wait(5.0)
        return phrase_for_hash(replay.state_hash), 1

    monkeypatch.setattr(exchange, "share_now", slow_share_now)
    phrase = exchange.share(run)
    assert started.wait(5.0)
    in_flight_thread = exchange._share_thread

    again = exchange.share(run)

    assert again == phrase
    assert exchange._share_thread is in_flight_thread
    release.set()
    exchange.wait_idle(5.0)
    assert calls == 1


# --- Code-Eingabe ----------------------------------------------------------------------


def test_code_entry_typing_and_validation(context: GameContext) -> None:
    scene = CodeEntryScene(context)
    _type(scene, "Apfel-BERG wolke!ß3")
    assert scene.text == "apfel-berg wolkess"
    scene.handle_event(_keydown(pygame.K_BACKSPACE))
    assert scene.text == "apfel-berg wolkes"
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene.message == HINT_FORMAT  # keine gültige Phrase
    scene.draw()
    scene.handle_event(_keydown(pygame.K_TAB))  # ohne Ergebnis: nichts
    assert scene._transition is None
    scene.handle_event(_keydown(pygame.K_ESCAPE))
    assert scene._transition is Transition.MAIN_MENU


def test_code_entry_keeps_f_as_a_letter(context: GameContext) -> None:
    """Der globale Vollbild-Shortcut `F` darf die Texteingabe nicht kapern."""
    scene = CodeEntryScene(context)
    assert not context.is_fullscreen
    scene.dispatch(_keydown(pygame.K_f, "f"))
    assert scene.text == "f"
    assert not context.is_fullscreen
    scene.dispatch(_keydown(pygame.K_F11, ""))  # F11 bleibt global
    assert context.is_fullscreen
    context.toggle_fullscreen()
    menu = MainMenu(context)
    menu.dispatch(_keydown(pygame.K_f, "f"))  # anderswo ist F weiter Vollbild
    assert context.is_fullscreen
    context.toggle_fullscreen()


def test_code_entry_offline_uses_local_store_only(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    run = _record(ticks=300)
    phrase = phrase_for_hash(run.state_hash)
    scene = CodeEntryScene(context)
    _type(scene, phrase)
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene.message == OFFLINE_LOCAL_ONLY
    store.save(share_name(phrase), replace(run, author="a" * 64))
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene.result is not None
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene._transition is Transition.START_RACE
    assert context.state.pending_replay == scene.result


def test_code_entry_fetches_and_offers_race_or_spectate(
    context: GameContext, relay: FakeRelay, tmp_path: Path
) -> None:
    friend = _exchange(relay, tmp_path / "friend")
    me = _exchange(relay, tmp_path / "me")
    context.replays = me.store
    context.exchange = me
    run = _record(ticks=600)
    phrase, _ = friend.share_now(run)

    scene = CodeEntryScene(context)
    _type(scene, f"  {phrase.upper()} ")
    scene.handle_event(_keydown(pygame.K_RETURN))
    assert scene.message == LOOKUP_SEARCHING
    assert scene.text == phrase
    scene.draw()
    _wait_lookup(scene, me)
    assert scene.result is not None
    assert scene.result.author == friend.identity.pubkey
    assert "LAUF VON" in scene.message
    scene.draw()

    scene.handle_event(_keydown(pygame.K_TAB))
    assert scene._transition is Transition.SPECTATE
    assert context.state.pending_replay == scene.result

    # Tippen nach dem Fund verwirft das Ergebnis.
    again = CodeEntryScene(context)
    _type(again, phrase)
    again.handle_event(_keydown(pygame.K_RETURN))
    _wait_lookup(again, me)
    assert again.result is not None  # aus dem Store, sofort
    _type(again, "x")
    assert again.result is None

    unknown = CodeEntryScene(context)
    _type(unknown, "abend abend abend")
    unknown.handle_event(_keydown(pygame.K_RETURN))
    _wait_lookup(unknown, me)
    assert unknown.result is None
    assert unknown.message == LOOKUP_NOT_FOUND


# --- Rennen & Zuschauen ------------------------------------------------------------------


def test_app_starts_race_and_spectate_from_pending_replay(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from meteorite_dash.app import App

    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    app = App()
    try:
        run = _record(ticks=120)
        app.context.state.pending_replay = run
        race = app._create_scene(Transition.START_RACE)
        assert isinstance(race, GameScene)
        assert race.seed == run.config.seed
        assert race.ghost is not None
        assert race.ghost.replay == run
        assert race.spectate is None
        assert app.context.state.pending_replay is None
        # Rennen unter den Regeln des Laufs: gleicher Modus und gleicher Director.
        assert race.mode is run.mode
        assert race.director_kind is run.director_kind
        assert race.recorder.director_kind is run.director_kind

        daily = replace(_record(ticks=120), mode=RunMode.DAILY, label="2026-08-30")
        app.context.state.pending_replay = daily
        daily_race = app._create_scene(Transition.START_RACE)
        assert isinstance(daily_race, GameScene)
        assert daily_race.mode is RunMode.DAILY
        assert daily_race.label == "2026-08-30"
        assert daily_race.ghost is not None
        assert daily_race.record_name() == "daily-2026-08-30"

        app.context.state.pending_replay = run
        watch = app._create_scene(Transition.SPECTATE)
        assert isinstance(watch, GameScene)
        assert watch.spectate == run
        assert watch.ghost is None

        assert isinstance(app._create_scene(Transition.START_RACE), MainMenu)  # nichts anstehend
        assert isinstance(app._create_scene(Transition.CODE_ENTRY), CodeEntryScene)
    finally:
        pygame.quit()


def test_spectate_replays_inputs_and_credits_nothing(context: GameContext, tmp_path: Path) -> None:
    store = ReplayStore(tmp_path)
    context.replays = store
    golden = replace(_golden_a(), author="f" * 64)
    scene = GameScene(context, spectate=golden)
    assert scene.sim.config == golden.config
    assert scene.director_kind is golden.director_kind  # Regeln des Replays, nicht des Modus
    coins_before = context.state.progress.coins
    ticks = 0
    while scene._transition is None:
        scene.update(SIM_DT)
        scene.draw()
        ticks += 1
        assert ticks <= golden.ticks + 1
    assert scene._transition is Transition.DEATH_SCREEN
    assert scene.sim.tick == golden.ticks
    assert scene.sim.state_hash() == golden.state_hash  # bit-gleich nachgespielt
    state = context.state
    assert state.final_spectate_author == "f" * 64
    assert state.final_light_years == golden.light_years
    assert state.last_replay is None
    assert scene.recorder.ticks == 0
    scene.on_exit()
    assert context.state.progress.coins == coins_before
    assert store.all() == []

    death = DeathScene(context)
    assert death._hint_line() == "TASTE: MENÜ"
    assert not death.can_share()
    death.draw()
    death.handle_event(_keydown(pygame.K_TAB))
    assert death._transition is Transition.MAIN_MENU


def test_spectate_ends_when_inputs_run_out(context: GameContext) -> None:
    run = _record(ticks=90)  # endet ohne Tod
    scene = GameScene(context, spectate=replace(run, author=""))
    for _ in range(run.ticks):
        scene.update(SIM_DT)
    assert scene._transition is None
    scene.update(SIM_DT)
    assert scene._transition is Transition.DEATH_SCREEN
    assert context.state.final_spectate_author == ""
    death = DeathScene(context)
    death.draw()  # "REPLAY VON DIR"


def test_death_screen_shares_code_on_c(
    context: GameContext, relay: FakeRelay, tmp_path: Path
) -> None:
    exchange = _exchange(relay, tmp_path)
    context.replays = exchange.store
    context.exchange = exchange
    scene = GameScene(context, seed=CONFIG.seed)
    for _ in range(120):
        scene.step(InputFrame.NONE)
    from meteorite_dash.entities import Meteorite

    scene.sim.entities.append(
        Meteorite(scene.sim.player.rect.copy(), 0.0, hp=10, contact_damage=999)
    )
    scene.step(InputFrame.NONE)
    exchange.wait_idle(10.0)  # Rekord-Publish
    assert len(relay.events) == 1

    death = DeathScene(context)
    assert death.can_share()
    assert "C: CODE TEILEN" in death._hint_line()
    death.handle_event(_keydown(pygame.K_c))
    assert death._transition is None  # bleibt auf dem Screen
    assert death._share_line().startswith("CODE: ")
    exchange.wait_idle(10.0)
    assert "GETEILT (1/1 RELAYS)" in death._share_line()
    assert len(relay.events) == 2  # Rekord + Code
    death.draw()
    death.handle_event(_keydown(pygame.K_RETURN))
    assert death._transition is Transition.MAIN_MENU

    # Neuer Lauf setzt den Code-Stand zurück.
    GameScene(context, seed=CONFIG.seed)
    assert death._share_line() == ""


def test_menu_offers_code_entry(context: GameContext) -> None:
    menu = MainMenu(context)
    index = [action for _, action in MENU_ITEMS].index("code")
    for _ in range(index):
        menu.handle_event(_keydown(pygame.K_DOWN))
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.CODE_ENTRY
    menu.draw()
