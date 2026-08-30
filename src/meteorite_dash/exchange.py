"""Community-Läufe: Bestläufe über Nostr teilen und fremde als Ghost holen.

Transport ist austauschbar (heute Relays, später QR/Text): jeder fremde Lauf
läuft durch denselben Trichter — Event prüfen, Share-Code entpacken,
Version/Seed/Länge prüfen, mit `headless.verify` nachspielen, erst dann in den
`ReplayStore` (`nostr-<seed>-<pubkey8>`, `Replay.author` = Pubkey). Ab da
gilt der normale Weg: `ReplayStore.best_for_seed` liefert den weitesten Lauf,
auch einen fremden, als Ghost.

Netz läuft in Hintergrund-Threads: das Menü holt die Läufe zum Tages-Seed im
Voraus (`prefetch`), der Spielstart wartet höchstens `NOSTR_FETCH_TIMEOUT`
(`wait_for`) und läuft sonst ohne fremde Ghosts los. Teilen (`publish`) ist
Feuer-und-vergessen; der Death-Screen zeigt den Stand (`publish_status`).
"""

import logging
import threading
from dataclasses import dataclass, replace

from meteorite_dash.config import NOSTR_MAX_TICKS, NOSTR_RELAYS, NOSTR_REPLAY_PREFIX, SIM_VERSION
from meteorite_dash.headless import verify
from meteorite_dash.identity import Identity, short_pubkey
from meteorite_dash.nostr import (
    ParsedRun,
    RelayClient,
    build_run_event,
    parse_run_event,
    run_filter,
)
from meteorite_dash.replay import Replay, ReplayStore

log = logging.getLogger(__name__)

STATUS_SEARCHING = "COMMUNITY: SUCHE LÄUFE …"
STATUS_OFFLINE = "COMMUNITY: OFFLINE"
STATUS_NONE = "COMMUNITY: NOCH KEINE FREMDEN LÄUFE"
PUBLISH_SHARING = "TEILE LAUF …"
PUBLISH_FAILED = "TEILEN FEHLGESCHLAGEN (OFFLINE?)"


@dataclass(frozen=True)
class ImportResult:
    fetched: int  # gültige fremde Läufe zum Seed (Signatur, Version, Länge)
    imported: int  # davon neu nachgespielt und gespeichert
    rejected: int  # verworfen: falsche Version/Seed, zu lang, Nachspielen weicht ab
    relays_ok: int

    @property
    def status(self) -> str:
        if self.relays_ok == 0:
            return STATUS_OFFLINE
        if self.fetched == 0:
            return STATUS_NONE
        text = f"COMMUNITY: {self.fetched} FREMDE LÄUFE"
        return f"{text} ({self.imported} NEU)" if self.imported else text


def replay_name(seed: int, pubkey: str) -> str:
    return f"{NOSTR_REPLAY_PREFIX}{seed}-{short_pubkey(pubkey)}"


class RunExchange:
    def __init__(
        self, identity: Identity, store: ReplayStore, *, client: RelayClient | None = None
    ) -> None:
        self.identity = identity
        self.store = store
        self.client = client if client is not None else RelayClient(NOSTR_RELAYS)
        self.status = ""  # Stand der letzten Suche, fürs Menü
        self.publish_status = ""  # Stand des letzten Teilens, für den Death-Screen
        self._fetch_thread: threading.Thread | None = None
        self._fetch_seed: int | None = None
        self._fetch_result: ImportResult | None = None
        self._publish_thread: threading.Thread | None = None

    # --- Holen ---------------------------------------------------------------------

    def prefetch(self, seed: int) -> None:
        """Startet die Suche im Hintergrund, falls nicht schon eine zu diesem Seed läuft."""
        thread = self._fetch_thread
        if thread is not None and thread.is_alive() and self._fetch_seed == seed:
            return
        self._fetch_seed = seed
        self._fetch_result = None
        self.status = STATUS_SEARCHING
        self._fetch_thread = threading.Thread(
            target=self._fetch_worker, args=(seed,), name="nostr-fetch", daemon=True
        )
        self._fetch_thread.start()

    def wait_for(self, seed: int, timeout: float) -> ImportResult | None:
        """Wartet höchstens `timeout` auf die Suche zu `seed` (startet sie bei Bedarf);
        `None`, wenn sie noch läuft — die Dateien kommen dann für den nächsten Lauf."""
        if self._fetch_thread is None or self._fetch_seed != seed:
            self.prefetch(seed)
        thread = self._fetch_thread
        assert thread is not None
        thread.join(timeout)
        if thread.is_alive():
            return None
        return self._fetch_result

    def import_runs(self, seed: int) -> ImportResult:
        """Synchron: holen, prüfen, speichern. Weiteste Läufe zuerst, damit der beste
        Ghost auch dann da ist, wenn die Zeit nicht für alle reicht."""
        result = self.client.fetch(run_filter(seed))
        candidates: list[ParsedRun] = []
        rejected = 0
        for event in result.events:
            parsed = parse_run_event(event)
            if parsed is None:
                rejected += 1
                continue
            if parsed.pubkey == self.identity.pubkey:
                continue  # eigener Lauf, liegt schon lokal
            if not self._acceptable(parsed.replay, seed):
                rejected += 1
                continue
            candidates.append(parsed)
        candidates.sort(key=lambda parsed: parsed.replay.light_years, reverse=True)

        imported = 0
        fetched = 0
        for parsed in candidates:
            name = replay_name(seed, parsed.pubkey)
            existing = self.store.load(name)
            if existing is not None and existing.state_hash == parsed.replay.state_hash:
                fetched += 1
                continue  # schon geprüft und gespeichert
            if not verify(parsed.replay).ok:
                log.warning("Lauf von %s zu Seed %d spielt nicht nach", parsed.pubkey[:8], seed)
                rejected += 1
                continue
            self.store.save(name, replace(parsed.replay, author=parsed.pubkey))
            imported += 1
            fetched += 1
        return ImportResult(fetched, imported, rejected, result.relays_ok)

    @staticmethod
    def _acceptable(replay: Replay, seed: int) -> bool:
        return (
            replay.sim_version == SIM_VERSION
            and replay.config.seed == seed
            and replay.ticks <= NOSTR_MAX_TICKS
        )

    def _fetch_worker(self, seed: int) -> None:
        try:
            result = self.import_runs(seed)
        except Exception:
            log.exception("Community-Suche zu Seed %d fehlgeschlagen", seed)
            result = ImportResult(0, 0, 0, 0)
        if self._fetch_seed != seed:
            return  # inzwischen läuft eine Suche zu einem anderen Seed
        self._fetch_result = result
        self.status = result.status

    # --- Teilen --------------------------------------------------------------------

    def publish(self, replay: Replay) -> None:
        """Feuer-und-vergessen im Hintergrund; Stand in `publish_status`."""
        self.publish_status = PUBLISH_SHARING
        self._publish_thread = threading.Thread(
            target=self._publish_worker, args=(replay,), name="nostr-publish", daemon=True
        )
        self._publish_thread.start()

    def publish_now(self, replay: Replay) -> int:
        """Synchron; liefert die Zahl der Relays, die den Lauf angenommen haben."""
        accepted = self.client.publish(build_run_event(self.identity, replay))
        if accepted:
            self.publish_status = f"LAUF GETEILT ({accepted}/{len(self.client.relays)} RELAYS)"
        else:
            self.publish_status = PUBLISH_FAILED
        return accepted

    def _publish_worker(self, replay: Replay) -> None:
        try:
            self.publish_now(replay)
        except Exception:
            log.exception("Teilen des Laufs fehlgeschlagen")
            self.publish_status = PUBLISH_FAILED

    def wait_idle(self, timeout: float) -> None:
        """Wartet auf laufende Hintergrund-Arbeit (Tests, sauberes Beenden)."""
        for thread in (self._fetch_thread, self._publish_thread):
            if thread is not None:
                thread.join(timeout)
