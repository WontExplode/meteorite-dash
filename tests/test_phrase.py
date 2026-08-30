"""Share-Phrase: eingefrorene Wortliste, Ableitung aus dem Hash, tolerante Eingabe."""

import hashlib
import re
from collections import Counter

from meteorite_dash.assets import data_path
from meteorite_dash.config import PHRASE_WORD_BITS, PHRASE_WORDS_FILE
from meteorite_dash.phrase import matches, normalize, phrase_for_hash, slug, words

# Festgenagelt: ändert sich der Hash, werden alte Codes ungültig (-> PHRASE_VERSION).
WORDLIST_SHA256 = "e8734fbef17598a893c194a682c785594919760aead56b58fbb07593fd204961"
HASH_A = "6571673fc82ead1576eb398b3a8736318b469c2b131d8f113f56978a04812df4"  # golden-a


def test_wordlist_is_frozen_and_clean() -> None:
    text = data_path(PHRASE_WORDS_FILE).read_text(encoding="utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == WORDLIST_SHA256
    table = words()
    assert len(table) == 1 << PHRASE_WORD_BITS == 2048
    assert len(set(table)) == len(table)
    assert list(table) == sorted(table)
    pattern = re.compile(r"^[a-z]{4,8}$")
    for word in table:
        assert pattern.match(word), word
        assert "ae" not in word and "oe" not in word, word
        # `ue` nur als Teil von au-e / eu-e / qu-e, nie als ü-Ersatz
        for i in range(1, len(word) - 1):
            if word[i : i + 2] == "ue":
                assert word[i - 1] in "aeq", word
    assert max(Counter(len(word) for word in table)) == 8


def test_phrase_is_derived_from_leading_hash_bits() -> None:
    phrase = phrase_for_hash(HASH_A)
    parts = phrase.split(" ")
    assert len(parts) == 3
    assert all(part in words() for part in parts)
    assert phrase_for_hash(HASH_A) == phrase  # deterministisch
    # Erste 33 Bit von 0x6571673fc82ead15: 0x6571673fc82ead15 >> 31
    bits = int(HASH_A[:16], 16) >> 31
    expected = [words()[(bits >> shift) & 2047] for shift in (22, 11, 0)]
    assert parts == expected
    assert phrase_for_hash("0" * 64) == "abend abend abend"
    assert phrase_for_hash("f" * 64) == "zyklop zyklop zyklop"
    assert phrase_for_hash("0" * 15 + "1" + "0" * 48) == "abend abend abend"  # Bit außerhalb
    assert phrase_for_hash("00000000" + "80000000" + "0" * 48) != "abend abend abend"


def test_normalize_is_tolerant_but_strict_about_words() -> None:
    phrase = phrase_for_hash(HASH_A)
    a, b, c = phrase.split(" ")
    assert normalize(f"  {a.upper()} - {b},{c}\n") == phrase
    assert normalize(f"{a}_{b}_{c}") == phrase
    assert normalize(f"{a} {b}") is None
    assert normalize(f"{a} {b} {c} {a}") is None
    assert normalize(f"{a} {b} xyzzy") is None
    assert normalize("") is None
    assert normalize("gross abend zyklop") == "gross abend zyklop"
    assert normalize("groß abend zyklop") == "gross abend zyklop"


def test_matches_and_slug() -> None:
    phrase = phrase_for_hash(HASH_A)
    assert matches(phrase.upper(), HASH_A)
    assert not matches(phrase, "0" * 64)
    assert not matches("kein code", HASH_A)
    assert slug("apfel berg wolke") == "apfel-berg-wolke"
