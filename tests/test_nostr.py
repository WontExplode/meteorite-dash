"""Community-Läufe über Nostr: Identität, Events, Relay-Client, Exchange und Szenen —
alles offline gegen einen Fake-Relay auf 127.0.0.1."""

import asyncio
import hashlib
import json
import stat
import sys
import threading
import time
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pygame
import pytest
from websockets.asyncio.server import ServerConnection, serve

from meteorite_dash import sharecode
from meteorite_dash.config import (
    IDENTITY_FILENAME,
    NOSTR_MAX_TICKS,
    NOSTR_REPLAY_PREFIX,
    NOSTR_RUN_KIND,
    OFFLINE_ENV,
    SAVE_DIR_ENV,
    SIM_VERSION,
)
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.entities import Meteorite
from meteorite_dash.exchange import (
    PUBLISH_FAILED,
    STATUS_NONE,
    STATUS_OFFLINE,
    ImportResult,
    RunExchange,
    replay_name,
)
from meteorite_dash.headless import scripted_inputs
from meteorite_dash.identity import Identity, IdentityStore, verify_signature
from meteorite_dash.inputs import InputFrame
from meteorite_dash.main import main
from meteorite_dash.nostr import (
    Event,
    RelayClient,
    build_run_event,
    event_id,
    parse_run_event,
    run_filter,
    run_tag,
)
from meteorite_dash.replay import Recorder, Replay, ReplayStore, RunMode
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.simulation import RunConfig, Simulation

SEED = 20260830
CONFIG = RunConfig(seed=SEED, ship="Allrounder")


def _record(config: RunConfig = CONFIG, input_seed: int = 3, ticks: int = 900) -> Replay:
    sim = Simulation(config)
    recorder = Recorder(config, mode=RunMode.DAILY, label="2026-08-30")
    for frame in scripted_inputs(input_seed, ticks):
        if sim.is_over:
            break
        recorder.record(frame)
        sim.step(frame)
    return recorder.finish(sim)


def _kill(scene: GameScene) -> None:
    rect = scene.sim.player.rect.copy()
    scene.sim.entities.append(Meteorite(rect, 0.0, hp=10, contact_damage=999))
    scene.step(InputFrame.NONE)


# --- Fake-Relay -------------------------------------------------------------------------


class FakeRelay:
    """Minimaler Relay: `EVENT` speichern (ersetzbar je Pubkey+Kind+`d`), `REQ` nach
    Kind und `#d` filtern, dann `EOSE`. Läuft in einem eigenen Thread."""

    def __init__(self) -> None:
        self.events: dict[tuple[str, int, str], Event] = {}
        self.port = 0
        self.received: list[list[object]] = []
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop: asyncio.Event | None = None
        self._thread = threading.Thread(target=self._run, name="fake-relay", daemon=True)

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.port}"

    def start(self) -> "FakeRelay":
        self._thread.start()
        assert self._ready.wait(5), "Fake-Relay startet nicht"
        return self

    def stop(self) -> None:
        if self._loop is not None and self._stop is not None:
            self._loop.call_soon_threadsafe(self._stop.set)
        self._thread.join(5)

    def _run(self) -> None:
        asyncio.run(self._serve())

    async def _serve(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._stop = asyncio.Event()
        async with serve(self._handle, "127.0.0.1", 0) as server:
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()
            await self._stop.wait()

    async def _handle(self, ws: ServerConnection) -> None:
        async for raw in ws:
            message = json.loads(raw)
            self.received.append(message)
            if message[0] == "EVENT":
                event = message[1]
                self._store(event)
                await ws.send(json.dumps(["OK", event["id"], True, ""]))
            elif message[0] == "REQ":
                sub, query = message[1], message[2]
                for event in self._matching(query):
                    await ws.send(json.dumps(["EVENT", sub, event]))
                await ws.send(json.dumps(["EOSE", sub]))

    def _store(self, event: Event) -> None:
        tags = event["tags"]
        assert isinstance(tags, list)
        d_tag = next((str(tag[1]) for tag in tags if tag[0] == "d"), "")
        key = (str(event["pubkey"]), _as_int(event["kind"]), d_tag)
        previous = self.events.get(key)
        if previous is None or _as_int(previous["created_at"]) <= _as_int(event["created_at"]):
            self.events[key] = event

    def _matching(self, query: dict[str, object]) -> list[Event]:
        kinds = query.get("kinds")
        d_tags = query.get("#d")
        return [
            event
            for (_, kind, d_tag), event in self.events.items()
            if (not isinstance(kinds, list) or kind in kinds)
            and (not isinstance(d_tags, list) or d_tag in d_tags)
        ]


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


@pytest.fixture
def relay() -> Iterator[FakeRelay]:
    fake = FakeRelay().start()
    yield fake
    fake.stop()


def _exchange(relay: FakeRelay, directory: Path, timeout: float = 5.0) -> RunExchange:
    identity = IdentityStore(directory / IDENTITY_FILENAME).load_or_create()
    store = ReplayStore(directory / "replays")
    return RunExchange(identity, store, client=RelayClient([relay.url], timeout=timeout))


# --- Identität --------------------------------------------------------------------------


def test_identity_signs_and_verifies() -> None:
    identity = Identity.generate()
    assert len(identity.pubkey) == 64
    assert identity.short == identity.pubkey[:8]
    digest = hashlib.sha256(b"hallo").digest()
    signature = identity.sign(digest)
    assert len(signature) == 64
    assert verify_signature(identity.pubkey, digest, signature)
    assert not verify_signature(identity.pubkey, hashlib.sha256(b"hallo!").digest(), signature)
    assert not verify_signature(Identity.generate().pubkey, digest, signature)
    assert not verify_signature("zz" * 32, digest, signature)
    assert not verify_signature(identity.pubkey, digest, b"kurz")
    with pytest.raises(ValueError):
        Identity(b"\x00" * 31)


def test_identity_store_creates_persists_and_tolerates_garbage(tmp_path: Path) -> None:
    path = tmp_path / "sub" / IDENTITY_FILENAME
    store = IdentityStore(path)
    assert store.load() is None
    identity = store.load_or_create()
    assert path.exists()
    if sys.platform != "win32":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    again = store.load_or_create()
    assert again.pubkey == identity.pubkey
    assert again.secret == identity.secret

    path.write_text("{kaputt", encoding="utf-8")
    assert store.load() is None
    fresh = store.load_or_create()
    assert fresh.pubkey != identity.pubkey
    assert store.load_or_create().pubkey == fresh.pubkey  # neu gespeichert

    for payload in (
        '{"format": 2, "secret": "00"}',
        '{"format": 1}',
        "[]",
        '{"format": 1, "secret": 5}',
    ):
        path.write_text(payload, encoding="utf-8")
        assert store.load() is None


# --- Events -----------------------------------------------------------------------------


def test_event_id_follows_nip01_serialization() -> None:
    tags = [["d", "meteorite-dash:1:1"], ["t", "meteorite-dash"]]
    serialized = '[0,"ab",1700000000,30078,[["d","meteorite-dash:1:1"],["t","meteorite-dash"]],"ü"]'
    expected = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    assert event_id("ab", 1700000000, 30078, tags, "ü") == expected


def test_build_and_parse_run_event() -> None:
    identity = Identity.generate()
    replay = _record()
    event = build_run_event(identity, replay, created_at=1_700_000_000)
    assert event["kind"] == NOSTR_RUN_KIND
    assert event["pubkey"] == identity.pubkey
    assert ["d", run_tag(SEED)] in event["tags"]  # type: ignore[operator]
    assert sharecode.from_text(str(event["content"])) == replay
    parsed = parse_run_event(event)
    assert parsed is not None
    assert parsed.pubkey == identity.pubkey
    assert parsed.created_at == 1_700_000_000
    assert parsed.replay == replay
    assert run_filter(SEED)["#d"] == [run_tag(SEED)]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda e: None,
        lambda e: [],
        lambda e: {k: v for k, v in e.items() if k != "sig"},
        lambda e: {**e, "kind": 1},
        lambda e: {**e, "created_at": e["created_at"] + 1},  # ID passt nicht mehr
        lambda e: {**e, "content": e["content"][:-4] + "AAAA"},  # Inhalt manipuliert
        lambda e: {**e, "sig": "0" * 128},
        lambda e: {**e, "pubkey": Identity.generate().pubkey},
        lambda e: {**e, "id": "zz" * 32},
        lambda e: {**e, "tags": [["d", "falsch"]]},
        lambda e: {**e, "tags": "keine"},
        lambda e: {**e, "content": "A" * 70_000},
    ],
)
def test_parse_run_event_rejects_garbage(mutate: object) -> None:
    event = build_run_event(Identity.generate(), _record(), created_at=1)
    assert parse_run_event(mutate(event)) is None  # type: ignore[operator]


def test_parse_rejects_resigned_event_with_wrong_d_tag() -> None:
    """Signatur gültig, aber `d`-Tag zeigt auf einen anderen Seed als der Inhalt."""
    identity = Identity.generate()
    replay = _record()
    tags = [["d", run_tag(SEED + 1)]]
    content = sharecode.to_text(replay)
    eid = event_id(identity.pubkey, 1, NOSTR_RUN_KIND, tags, content)
    event: Event = {
        "id": eid,
        "pubkey": identity.pubkey,
        "created_at": 1,
        "kind": NOSTR_RUN_KIND,
        "tags": tags,
        "content": content,
        "sig": identity.sign(bytes.fromhex(eid)).hex(),
    }
    assert parse_run_event(event) is None


# --- Relay-Client -----------------------------------------------------------------------


def test_relay_client_publishes_and_fetches(relay: FakeRelay) -> None:
    client = RelayClient([relay.url], timeout=5.0)
    identity = Identity.generate()
    first = build_run_event(identity, _record(ticks=300), created_at=10)
    assert client.publish(first) == 1
    result = client.fetch(run_filter(SEED))
    assert result.relays_ok == 1
    assert result.events == [first]

    # Ersetzbar: derselbe `d`-Tag vom selben Pubkey ersetzt den alten Lauf.
    second = build_run_event(identity, _record(ticks=600), created_at=11)
    assert client.publish(second) == 1
    assert client.fetch(run_filter(SEED)).events == [second]
    assert client.fetch(run_filter(SEED + 1)).events == []
    # CLOSE nach EOSE, damit das Relay die Subscription freigibt.
    assert ["CLOSE", "runs"] in relay.received


def test_relay_client_survives_unreachable_relay(relay: FakeRelay) -> None:
    dead = "ws://127.0.0.1:1"
    client = RelayClient([dead, relay.url], timeout=2.0)
    event = build_run_event(Identity.generate(), _record(), created_at=1)
    started = time.monotonic()
    assert client.publish(event) == 1
    result = client.fetch(run_filter(SEED))
    assert result.relays_ok == 1
    assert result.events == [event]
    assert time.monotonic() - started < 8.0

    only_dead = RelayClient([dead], timeout=1.0)
    assert only_dead.publish(event) == 0
    assert only_dead.fetch(run_filter(SEED)).relays_ok == 0


# --- Exchange ---------------------------------------------------------------------------


def test_exchange_shares_and_imports_verified_runs(relay: FakeRelay, tmp_path: Path) -> None:
    alice = _exchange(relay, tmp_path / "alice")
    bob = _exchange(relay, tmp_path / "bob")
    run = _record(ticks=1200)
    assert alice.publish_now(run) == 1
    assert alice.publish_status.startswith("LAUF GETEILT (1/1")

    result = bob.import_runs(SEED)
    assert result == ImportResult(fetched=1, imported=1, rejected=0, relays_ok=1)
    assert "1 FREMDE LÄUFE (1 NEU)" in result.status
    name = replay_name(SEED, alice.identity.pubkey)
    assert name.startswith(NOSTR_REPLAY_PREFIX)
    imported = bob.store.load(name)
    assert imported is not None
    assert imported.author == alice.identity.pubkey
    assert replace(imported, author="") == run
    assert bob.store.best_for_seed(SEED) == imported

    # Zweiter Import: schon da, nichts Neues, kein erneutes Nachspielen.
    assert bob.import_runs(SEED) == ImportResult(1, 0, 0, 1)
    # Eigene Läufe werden übersprungen.
    assert alice.import_runs(SEED) == ImportResult(0, 0, 0, 1)


def test_exchange_rejects_runs_that_do_not_replay(relay: FakeRelay, tmp_path: Path) -> None:
    cheater = _exchange(relay, tmp_path / "cheater")
    honest = _exchange(relay, tmp_path / "honest")
    run = _record(ticks=600)
    faked = replace(run, final=run.final._replace(light_years=run.light_years + 500))
    assert cheater.publish_now(faked) == 1  # der Relay prüft nur die Signatur
    result = honest.import_runs(SEED)
    assert result == ImportResult(fetched=0, imported=0, rejected=1, relays_ok=1)
    assert honest.store.all() == []


def test_exchange_filters_version_seed_and_length(relay: FakeRelay, tmp_path: Path) -> None:
    sender = _exchange(relay, tmp_path / "sender")
    receiver = _exchange(relay, tmp_path / "receiver")
    run = _record(ticks=600)
    too_long = replace(run, frames=((0, NOSTR_MAX_TICKS + 1),))
    old_version = replace(run, sim_version=SIM_VERSION + 1)
    # Alle drei landen unter verschiedenen `d`-Tags bzw. werden beim Import gefiltert.
    for candidate in (too_long, old_version):
        assert sender.publish_now(candidate) == 1
    result = receiver.import_runs(SEED)
    assert result.imported == 0
    assert result.rejected == 1  # zu lang; alte Version hängt unter einem anderen `d`-Tag
    assert receiver.import_runs(run.config.seed + 1) == ImportResult(0, 0, 0, 1)


def test_exchange_offline_status(tmp_path: Path) -> None:
    identity = Identity.generate()
    exchange = RunExchange(
        identity, ReplayStore(tmp_path), client=RelayClient(["ws://127.0.0.1:1"], timeout=1.0)
    )
    result = exchange.import_runs(SEED)
    assert result.relays_ok == 0
    assert result.status == STATUS_OFFLINE
    assert exchange.publish_now(_record(ticks=120)) == 0
    assert exchange.publish_status == PUBLISH_FAILED
    assert ImportResult(0, 0, 0, 1).status == STATUS_NONE


def test_exchange_prefetch_and_wait(relay: FakeRelay, tmp_path: Path) -> None:
    sender = _exchange(relay, tmp_path / "sender")
    sender.publish_now(_record(ticks=300))
    receiver = _exchange(relay, tmp_path / "receiver")
    receiver.prefetch(SEED)
    assert receiver.status  # "SUCHE" oder schon fertig
    result = receiver.wait_for(SEED, timeout=10.0)
    assert result is not None
    assert result.imported == 1
    assert receiver.status == result.status
    # Anderer Seed -> neue Suche.
    other = receiver.wait_for(SEED + 1, timeout=10.0)
    assert other == ImportResult(0, 0, 0, 1)


# --- Szenen -----------------------------------------------------------------------------


def test_game_scene_publishes_new_records_only(
    context: GameContext, relay: FakeRelay, tmp_path: Path
) -> None:
    exchange = _exchange(relay, tmp_path)
    context.replays = exchange.store
    context.exchange = exchange

    first = GameScene(context, seed=SEED)
    for _ in range(300):
        first.step(InputFrame.NONE)
    _kill(first)
    exchange.wait_idle(10.0)
    assert len(relay.events) == 1
    assert exchange.publish_status.startswith("LAUF GETEILT")

    worse = GameScene(context, seed=SEED)
    _kill(worse)
    exchange.wait_idle(10.0)
    assert len(relay.events) == 1  # kein Rekord, nichts gesendet
    stored = next(iter(relay.events.values()))
    assert parse_run_event(stored) is not None


def test_ghost_from_community_run_and_death_screen(
    context: GameContext, relay: FakeRelay, tmp_path: Path
) -> None:
    friend = _exchange(relay, tmp_path / "friend")
    friend.publish_now(_record(ticks=1200))
    me = _exchange(relay, tmp_path / "me")
    context.replays = me.store
    context.exchange = me
    assert me.wait_for(SEED, timeout=10.0) is not None

    scene = GameScene(context, seed=SEED)
    assert scene.ghost is not None
    assert scene.ghost.replay.author == friend.identity.pubkey
    _kill(scene)
    state = context.state
    assert state.final_record_author == friend.identity.pubkey
    death = DeathScene(context)
    line, _ = death._record_line()
    assert f"VON {friend.identity.short}" in line
    # Eigener erster Lauf = eigener Rekord -> wird geteilt, Community-Ghost hin oder her.
    assert death._share_line()
    me.wait_idle(10.0)
    assert death._share_line().startswith("LAUF GETEILT")
    death.draw()
    # Nächster Lauf setzt den Stand zurück.
    GameScene(context, seed=SEED)
    assert death._share_line() == ""


def test_main_menu_prefetches_daily_seed(
    context: GameContext, relay: FakeRelay, tmp_path: Path
) -> None:
    exchange = _exchange(relay, tmp_path)
    context.exchange = exchange
    menu = MainMenu(context)
    menu.on_enter()
    assert exchange.wait_for(daily_seed(today_utc()), timeout=10.0) is not None
    menu.draw()  # Status-Zeile zeichnen
    assert exchange.status == STATUS_NONE


def test_app_without_network_when_offline_env_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from meteorite_dash.app import App

    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv(OFFLINE_ENV, "1")
    app = App()
    try:
        assert app.context.exchange is None
        assert not (tmp_path / IDENTITY_FILENAME).exists()
    finally:
        pygame.quit()


def test_cli_publish_and_fetch(
    monkeypatch: pytest.MonkeyPatch,
    relay: FakeRelay,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import meteorite_dash.config as config
    import meteorite_dash.exchange as exchange_module

    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path / "sender"))
    monkeypatch.setattr(config, "NOSTR_RELAYS", (relay.url,))
    monkeypatch.setattr(exchange_module, "NOSTR_RELAYS", (relay.url,))
    run = _record(ticks=600)
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run.to_dict()), encoding="utf-8")
    assert main(["--publish", str(path)]) == 0
    assert "LAUF GETEILT" in capsys.readouterr().out

    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path / "receiver"))
    assert main(["--fetch", str(SEED)]) == 0
    out = capsys.readouterr().out
    assert "neu=1" in out
    assert (tmp_path / "receiver" / "replays").glob(f"{NOSTR_REPLAY_PREFIX}*")

    tampered = replace(run, state_hash="0" * 64)
    path.write_text(json.dumps(tampered.to_dict()), encoding="utf-8")
    assert main(["--publish", str(path)]) == 1
