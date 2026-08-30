"""Nostr-Protokoll (NIP-01 / NIP-78) für geteilte Läufe — ohne eigenen Server.

Ein Lauf ist ein ersetzbares Event `kind:30078` mit `d`-Tag
`meteorite-dash:<sim_version>:<seed>`: pro Pubkey und Seed hält jedes Relay
genau einen Lauf, den zuletzt veröffentlichten. Inhalt ist der Share-Code
(`sharecode.py`). Relays prüfen Signaturen beim Annehmen; `parse_run_event`
prüft sie beim Lesen trotzdem noch einmal — ob der Lauf echt ist, beweist
danach ohnehin erst `headless.verify` (siehe `exchange.py`).

`RelayClient` spricht über `websockets` mit mehreren Relays parallel. Netz
ist feindlich: jede Verbindung hat ein Timeout, jeder Fehler wird geloggt und
zählt als „Relay nicht erreichbar" — nie eine Exception nach außen.
"""

import asyncio
import hashlib
import json
import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import NamedTuple

from websockets.asyncio.client import connect

from meteorite_dash import sharecode
from meteorite_dash.config import (
    NOSTR_APP_TAG,
    NOSTR_MAX_CONTENT_CHARS,
    NOSTR_MAX_RUNS,
    NOSTR_RUN_KIND,
    NOSTR_TIMEOUT,
    SIM_VERSION,
)
from meteorite_dash.identity import Identity, verify_signature
from meteorite_dash.replay import Replay

log = logging.getLogger(__name__)

Event = dict[str, object]
Filter = dict[str, object]
Tags = list[list[str]]

_SUBSCRIPTION_ID = "runs"
_CLOSE_TIMEOUT = 1.0


# --- Events -------------------------------------------------------------------------------


def run_tag(seed: int, sim_version: int = SIM_VERSION) -> str:
    return f"{NOSTR_APP_TAG}:{sim_version}:{seed}"


def run_filter(seed: int, *, limit: int = NOSTR_MAX_RUNS) -> Filter:
    return {"kinds": [NOSTR_RUN_KIND], "#d": [run_tag(seed)], "limit": limit}


def event_id(pubkey: str, created_at: int, kind: int, tags: Tags, content: str) -> str:
    """NIP-01: SHA-256 über `[0, pubkey, created_at, kind, tags, content]` ohne
    Whitespace und ohne `\\uXXXX`-Escapes für Nicht-ASCII."""
    payload = json.dumps(
        [0, pubkey, created_at, kind, tags, content], separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_run_event(identity: Identity, replay: Replay, *, created_at: int | None = None) -> Event:
    if created_at is None:
        created_at = int(time.time())
    tags: Tags = [
        ["d", run_tag(replay.config.seed, replay.sim_version)],
        ["t", NOSTR_APP_TAG],
        # NIP-31: lesbarer Hinweis für Clients, die den Kind nicht kennen.
        [
            "alt",
            f"Meteorite Dash run: {replay.light_years:.0f} light-years, seed {replay.config.seed}",
        ],
    ]
    content = sharecode.to_text(replay)
    eid = event_id(identity.pubkey, created_at, NOSTR_RUN_KIND, tags, content)
    return {
        "id": eid,
        "pubkey": identity.pubkey,
        "created_at": created_at,
        "kind": NOSTR_RUN_KIND,
        "tags": tags,
        "content": content,
        "sig": identity.sign(bytes.fromhex(eid)).hex(),
    }


class ParsedRun(NamedTuple):
    pubkey: str
    created_at: int
    replay: Replay


def parse_run_event(data: object) -> ParsedRun | None:
    """Defensiv wie `Replay.from_dict`: falsche Form, falscher Kind, falsche ID,
    falsche Signatur, unlesbarer Share-Code oder `d`-Tag ≠ Inhalt -> `None`."""
    if not isinstance(data, dict):
        return None
    try:
        pubkey = _hex(data["pubkey"], 64)
        eid = _hex(data["id"], 64)
        sig = _hex(data["sig"], 128)
        created_at = _int(data["created_at"])
        kind = _int(data["kind"])
        content = data["content"]
        tags = _tags(data["tags"])
    except (KeyError, TypeError, ValueError):
        return None
    if not isinstance(content, str) or len(content) > NOSTR_MAX_CONTENT_CHARS:
        return None
    if kind != NOSTR_RUN_KIND:
        return None
    if event_id(pubkey, created_at, kind, tags, content) != eid:
        return None
    if not verify_signature(pubkey, bytes.fromhex(eid), bytes.fromhex(sig)):
        return None
    replay = sharecode.from_text(content)
    if replay is None:
        return None
    expected_tag = run_tag(replay.config.seed, replay.sim_version)
    if ["d", expected_tag] not in tags:
        return None
    return ParsedRun(pubkey, created_at, replay)


def _hex(value: object, length: int) -> str:
    if not isinstance(value, str) or len(value) != length:
        raise ValueError("Hex-Feld hat die falsche Länge")
    bytes.fromhex(value)  # ValueError bei Nicht-Hex
    return value


def _int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("int erwartet")
    return value


def _tags(value: object) -> Tags:
    if not isinstance(value, list):
        raise TypeError("tags: Liste erwartet")
    tags: Tags = []
    for tag in value:
        if not isinstance(tag, list) or not all(isinstance(item, str) for item in tag):
            raise TypeError("tag: Liste von Strings erwartet")
        tags.append(list(tag))
    return tags


# --- Relays -------------------------------------------------------------------------------


@dataclass(frozen=True)
class FetchResult:
    events: list[Event]
    relays_ok: int  # Relays, die geantwortet haben (auch mit null Events)


class RelayClient:
    """Sendet/holt Events an/von mehreren Relays parallel; blockierend, mit eigenem
    Event-Loop je Aufruf — gedacht für einen Hintergrund-Thread."""

    def __init__(self, relays: Sequence[str], *, timeout: float = NOSTR_TIMEOUT) -> None:
        self.relays = tuple(relays)
        self.timeout = timeout

    def publish(self, event: Event) -> int:
        """Anzahl der Relays, die das Event angenommen haben (`OK … true`)."""
        return asyncio.run(self._publish_all(event))

    def fetch(self, query: Filter) -> FetchResult:
        """Alle Events zum Filter, über Relays vereinigt und nach ID dedupliziert."""
        return asyncio.run(self._fetch_all(query))

    async def _publish_all(self, event: Event) -> int:
        results = await asyncio.gather(*(self._publish_one(url, event) for url in self.relays))
        return sum(results)

    async def _publish_one(self, url: str, event: Event) -> bool:
        message = json.dumps(["EVENT", event], separators=(",", ":"), ensure_ascii=False)
        try:
            async with (
                asyncio.timeout(self.timeout),
                connect(url, open_timeout=self.timeout, close_timeout=_CLOSE_TIMEOUT) as ws,
            ):
                await ws.send(message)
                async for raw in ws:
                    reply = _message(raw)
                    if reply is None or len(reply) < 3 or reply[0] != "OK":
                        continue
                    if reply[1] != event["id"]:
                        continue
                    accepted = reply[2] is True
                    if not accepted:
                        log.info("Relay %s lehnt Event ab: %s", url, reply[3:])
                    return accepted
        except Exception as exc:  # Netz: alles fangen, nie crashen
            log.info("Relay %s (publish): %s", url, _describe(exc))
        return False

    async def _fetch_all(self, query: Filter) -> FetchResult:
        results = await asyncio.gather(*(self._fetch_one(url, query) for url in self.relays))
        merged: dict[object, Event] = {}
        relays_ok = 0
        for events in results:
            if events is None:
                continue
            relays_ok += 1
            for event in events:
                merged.setdefault(event.get("id"), event)
        return FetchResult(list(merged.values()), relays_ok)

    async def _fetch_one(self, url: str, query: Filter) -> list[Event] | None:
        """`None` = Relay nicht erreichbar; sonst die Events bis `EOSE` (oder bis zum
        Timeout, dann das bis dahin Erhaltene)."""
        request = json.dumps(["REQ", _SUBSCRIPTION_ID, query], separators=(",", ":"))
        events: list[Event] = []
        try:
            async with (
                asyncio.timeout(self.timeout),
                connect(url, open_timeout=self.timeout, close_timeout=_CLOSE_TIMEOUT) as ws,
            ):
                await ws.send(request)
                async for raw in ws:
                    reply = _message(raw)
                    if reply is None or len(reply) < 2 or reply[1] != _SUBSCRIPTION_ID:
                        continue
                    if reply[0] == "EVENT" and len(reply) >= 3 and isinstance(reply[2], dict):
                        events.append(reply[2])
                    elif reply[0] in ("EOSE", "CLOSED"):
                        break
                await ws.send(json.dumps(["CLOSE", _SUBSCRIPTION_ID]))
        except TimeoutError:
            log.info("Relay %s (fetch): Timeout nach %d Events", url, len(events))
        except Exception as exc:
            log.info("Relay %s (fetch): %s", url, _describe(exc))
            return None
        return events


def _message(raw: str | bytes) -> list[object] | None:
    try:
        parsed: object = json.loads(raw)
    except ValueError:
        return None
    return parsed if isinstance(parsed, list) else None


def _describe(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
