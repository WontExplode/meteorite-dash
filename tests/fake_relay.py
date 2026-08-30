"""Minimaler Nostr-Relay für Tests: `EVENT` speichern (ersetzbar je Pubkey+Kind+`d`),
`REQ` nach Kind und `#d` filtern, dann `EOSE`. Läuft in einem eigenen Thread auf
127.0.0.1 — kein Test braucht das Netz."""

import asyncio
import json
import threading

from websockets.asyncio.server import ServerConnection, serve

from meteorite_dash.nostr import Event


def _as_int(value: object) -> int:
    assert isinstance(value, int)
    return value


class FakeRelay:
    def __init__(self, *, flood: int = 0) -> None:
        # `flood` > 0: bösartiges Relay — so viele Events auf jedes `REQ`, ohne `EOSE`.
        self.flood = flood
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
                if self.flood:
                    await self._flood(ws, sub)
                    continue
                for event in self._matching(query):
                    await ws.send(json.dumps(["EVENT", sub, event]))
                await ws.send(json.dumps(["EOSE", sub]))

    async def _flood(self, ws: ServerConnection, sub: object) -> None:
        """Ignoriert `limit` und schickt Events ohne `EOSE`; der Client muss deckeln.
        Bricht ab, sobald er die Verbindung schließt."""
        try:
            for index in range(self.flood):
                await ws.send(json.dumps(["EVENT", sub, {"id": f"{index:064x}"}]))
        except Exception:  # Client hat gedeckelt und aufgelegt
            pass

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
