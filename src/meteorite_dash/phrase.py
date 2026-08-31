"""Share-Phrase: drei deutsche Wörter als Adresse eines geteilten Laufs.

Die Phrase wird aus dem Lauf selbst abgeleitet — die ersten 33 Bit des
`state_hash` wählen drei Wörter aus einer Liste von 2048 (`words_de.txt`,
kleingeschrieben, ASCII, 4-8 Buchstaben): 2048³ ≈ 8,6 Milliarden Kombinationen.
Deterministisch heißt: gleicher Lauf, gleiche Phrase, nichts zu speichern; und
wer einen Lauf unter einer Phrase erhält, prüft mit `matches`, dass Hash und
Phrase zusammenpassen — das fängt Kollisionen und untergeschobene Läufe.

Die Phrase ist eine Adresse, kein Passwort: Läufe auf Nostr sind öffentlich.

Die Wortliste ist eingefroren. Jede Änderung (Wort, Reihenfolge, Ableitung)
macht alte Phrasen ungültig → `PHRASE_VERSION` erhöhen, das ist eine neue Serie.
"""

import functools
import re

from meteorite_dash.assets import data_path
from meteorite_dash.config import PHRASE_WORD_BITS, PHRASE_WORD_COUNT, PHRASE_WORDS_FILE

_SEPARATORS = re.compile(r"[\s,;/+\-_.]+")
_HASH_HEX_DIGITS = 16  # 64 Bit reichen für 3 x 11 Bit


@functools.cache
def words() -> tuple[str, ...]:
    text = data_path(PHRASE_WORDS_FILE).read_text(encoding="utf-8")
    result = tuple(text.split())
    if len(result) != 1 << PHRASE_WORD_BITS:
        raise RuntimeError(
            f"{PHRASE_WORDS_FILE}: {len(result)} Wörter, erwartet {1 << PHRASE_WORD_BITS}"
        )
    return result


@functools.cache
def _index() -> frozenset[str]:
    return frozenset(words())


def phrase_for_hash(state_hash: str) -> str:
    """Drei Wörter aus den führenden Bits eines SHA-256-Hex-Strings."""
    value = int(state_hash[:_HASH_HEX_DIGITS], 16)
    total_bits = PHRASE_WORD_COUNT * PHRASE_WORD_BITS
    bits = value >> (_HASH_HEX_DIGITS * 4 - total_bits)
    mask = (1 << PHRASE_WORD_BITS) - 1
    table = words()
    picks = [
        table[(bits >> (PHRASE_WORD_BITS * (PHRASE_WORD_COUNT - 1 - i))) & mask]
        for i in range(PHRASE_WORD_COUNT)
    ]
    return " ".join(picks)


def normalize(text: str) -> str | None:
    """Nutzereingabe -> kanonische Phrase (`w1 w2 w3`) oder `None`.

    Tolerant bei Groß-/Kleinschreibung, Trennzeichen und `ß`; streng bei der
    Wortzahl und bei Wörtern, die nicht in der Liste stehen.

    >>> normalize("  ABEND-abfahrt  Abstand ")
    'abend abfahrt abstand'

    Alles, was keine gültige Phrase ist, kommt als `None` zurück — die
    `CodeEntryScene` zeigt dann einen Hinweis, statt abzustürzen:

    >>> normalize("abend abfahrt") is None
    True
    >>> normalize("abend abfahrt kaesekuchen") is None
    True
    >>> normalize("") is None
    True
    """
    cleaned = text.strip().lower().replace("ß", "ss")
    parts = [part for part in _SEPARATORS.split(cleaned) if part]
    if len(parts) != PHRASE_WORD_COUNT or any(part not in _index() for part in parts):
        return None
    return " ".join(parts)


def matches(phrase: str, state_hash: str) -> bool:
    return normalize(phrase) == phrase_for_hash(state_hash)


def slug(phrase: str) -> str:
    """Phrase als Dateinamen-/Tag-tauglicher String: `apfel-berg-wolke`."""
    return phrase.replace(" ", "-")
