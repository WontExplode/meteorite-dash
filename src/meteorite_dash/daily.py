"""Daily Run (Issue #34): ein gemeinsamer Seed pro UTC-Tag.

Kein Server, keine Uhrzeit-Synchronisation: `daily_seed(day)` ist ein SHA-256
aus `DAILY_SEED_SALT` und dem ISO-Datum, auf `SEED_BITS` gekürzt. Wer am
selben Tag spielt, bekommt dieselbe Spawn-Folge — bis die eigenen Eingaben
sie verändern. Der beste Lauf des Tages liegt als `daily-<datum>.json` im
`ReplayStore` und fliegt beim nächsten Versuch als Ghost mit.
"""

import hashlib
from datetime import UTC, date, datetime

from meteorite_dash.config import DAILY_REPLAY_PREFIX, DAILY_SEED_SALT, SEED_BITS


def today_utc() -> date:
    """Heutiges Datum in UTC — der Tageswechsel gilt für alle gleichzeitig."""
    return datetime.now(UTC).date()


def daily_seed(day: date) -> int:
    """Seed des Tages: SHA-256 über Salt und ISO-Datum, auf `SEED_BITS` gekürzt.

    >>> from datetime import date
    >>> daily_seed(date(2026, 8, 31))
    1484649728

    Der Wert hängt nur am Datum — deshalb spielen alle denselben Lauf, ohne
    dass ein Server ihn verteilt:

    >>> daily_seed(date(2026, 8, 31)) == daily_seed(date(2026, 8, 31))
    True
    >>> daily_seed(date(2026, 8, 31)) == daily_seed(date(2026, 9, 1))
    False
    """
    digest = hashlib.sha256(f"{DAILY_SEED_SALT}:{day.isoformat()}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % (1 << SEED_BITS)


def daily_replay_name(day: date) -> str:
    """Name des Tagesrekords im `ReplayStore`: `daily-<datum>`.

    >>> from datetime import date
    >>> daily_replay_name(date(2026, 8, 31))
    'daily-2026-08-31'
    """
    return f"{DAILY_REPLAY_PREFIX}{day.isoformat()}"
