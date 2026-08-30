"""Entry-Point: Spiel starten oder mit `--verify` ein Replay headless prüfen."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from meteorite_dash.exchange import RunExchange


def main(argv: Sequence[str] | None = None) -> int:
    """Parst die Kommandozeile; ohne `--verify` startet die `App`. Liefert den Exit-Code."""
    parser = argparse.ArgumentParser(prog="meteorite-dash", description="Meteorite Dash")
    parser.add_argument(
        "--verify",
        metavar="REPLAY.json",
        help="Replay headless nachspielen, Trace ausgeben und Endzustand prüfen (kein Fenster)",
    )
    parser.add_argument(
        "--publish",
        metavar="REPLAY.json",
        help="Replay als eigenen Bestlauf an die Nostr-Relays senden (kein Fenster)",
    )
    parser.add_argument(
        "--fetch",
        metavar="SEED",
        type=int,
        help="fremde Läufe zu diesem Seed von den Relays holen, prüfen und ablegen",
    )
    args = parser.parse_args(argv)
    if args.verify is not None:
        return verify_command(Path(args.verify))
    if args.publish is not None:
        return publish_command(Path(args.publish))
    if args.fetch is not None:
        return fetch_command(args.fetch)

    from meteorite_dash.app import App

    App().run()
    return 0


def verify_command(path: Path) -> int:
    """Exit-Code 0 = bit-gleich nachgespielt, 1 = Abweichung oder unlesbar."""
    from meteorite_dash.config import SIM_VERSION
    from meteorite_dash.headless import format_trace, verify
    from meteorite_dash.replay import Replay

    try:
        replay = Replay.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"FAIL {path}: nicht lesbar ({exc})")
        return 1
    if replay is None:
        print(f"FAIL {path}: kein gültiges Replay")
        return 1

    result = verify(replay)
    print(format_trace(result.trace))
    print(
        f"seed={replay.config.seed} ship={replay.config.ship} ticks={replay.ticks} "
        f"sim_version={replay.sim_version} (aktuell {SIM_VERSION})"
    )
    if not result.version_matches:
        print("FAIL Replay stammt aus einer anderen Simulations-Version")
        return 1
    if result.ok:
        print(f"PASS Endzustand und Hash identisch ({result.trace.state_hash[:16]})")
        return 0
    print(
        f"FAIL erwartet {replay.final} / {replay.state_hash[:16]}, "
        f"nachgespielt {result.trace.final} / {result.trace.state_hash[:16]}"
    )
    return 1


def _exchange() -> "RunExchange":
    from meteorite_dash.config import IDENTITY_FILENAME
    from meteorite_dash.exchange import RunExchange
    from meteorite_dash.identity import IdentityStore
    from meteorite_dash.persistence import default_save_dir
    from meteorite_dash.replay import ReplayStore, default_replay_dir

    identity = IdentityStore(default_save_dir() / IDENTITY_FILENAME).load_or_create()
    return RunExchange(identity, ReplayStore(default_replay_dir()))


def publish_command(path: Path) -> int:
    """Exit-Code 0 = mindestens ein Relay hat den Lauf angenommen."""
    from meteorite_dash.headless import verify
    from meteorite_dash.replay import Replay

    try:
        replay = Replay.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        print(f"FAIL {path}: nicht lesbar ({exc})")
        return 1
    if replay is None or not verify(replay).ok:
        print(f"FAIL {path}: kein gültiges Replay oder spielt nicht nach")
        return 1
    exchange = _exchange()
    accepted = exchange.publish_now(replay)
    print(f"{exchange.identity.short}: {exchange.publish_status}")
    return 0 if accepted else 1


def fetch_command(seed: int) -> int:
    """Exit-Code 0 = mindestens ein Relay hat geantwortet."""
    exchange = _exchange()
    result = exchange.import_runs(seed)
    print(
        f"seed={seed} relays={result.relays_ok} läufe={result.fetched} "
        f"neu={result.imported} verworfen={result.rejected}"
    )
    print(result.status)
    return 0 if result.relays_ok else 1


if __name__ == "__main__":
    sys.exit(main())
