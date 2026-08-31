"""Fortschritt, Shop-Regeln und Datei-Persistenz (Issue #14)."""

import json
from pathlib import Path

import pytest

from meteorite_dash.accessories import ACCESSORIES, ACCESSORIES_BY_ID, AccessoryKind
from meteorite_dash.config import (
    ACCESSORY_MAX_STOCK,
    SAVE_DIR_ENV,
    SAVE_FILENAME,
    SAVE_FORMAT_VERSION,
)
from meteorite_dash.persistence import SaveStore, default_save_dir, default_save_path
from meteorite_dash.progress import Progress, ShopResult
from meteorite_dash.ships import SHIPS, SHIPS_BY_NAME, TINTS, TINTS_BY_ID

ALLROUNDER = SHIPS_BY_NAME["Allrounder"]
BRAWLER = SHIPS_BY_NAME["Brawler"]
RACER = SHIPS_BY_NAME["Racer"]
SHIELD = ACCESSORIES_BY_ID["shield"]
MAGNET = ACCESSORIES_BY_ID["magnet"]
ARMOR = ACCESSORIES_BY_ID["armor"]
GOLD = TINTS_BY_ID["gold"]


# --- Katalog ------------------------------------------------------------------


def test_exactly_one_ship_is_free() -> None:
    assert [spec.name for spec in SHIPS if spec.is_free] == ["Allrounder"]


def test_catalog_ids_are_unique() -> None:
    assert len(ACCESSORIES_BY_ID) == len(ACCESSORIES)
    assert len(TINTS_BY_ID) == len(TINTS)
    assert {spec.kind for spec in ACCESSORIES} == set(AccessoryKind)


# --- Progress: Kaufen -----------------------------------------------------------


def test_fresh_progress_unlocks_only_free_ships() -> None:
    progress = Progress()
    assert progress.coins == 0
    assert progress.is_ship_unlocked(ALLROUNDER)
    assert not progress.is_ship_unlocked(BRAWLER)


def test_buy_ship_deducts_coins_and_unlocks() -> None:
    progress = Progress(coins=BRAWLER.price)
    assert progress.buy_ship(BRAWLER) is ShopResult.OK
    assert progress.coins == 0
    assert progress.is_ship_unlocked(BRAWLER)
    assert progress.buy_ship(BRAWLER) is ShopResult.ALREADY_OWNED


def test_buy_ship_too_expensive_keeps_coins() -> None:
    progress = Progress(coins=BRAWLER.price - 1)
    assert progress.buy_ship(BRAWLER) is ShopResult.TOO_EXPENSIVE
    assert progress.coins == BRAWLER.price - 1
    assert not progress.is_ship_unlocked(BRAWLER)


def test_free_ship_is_always_owned() -> None:
    progress = Progress(coins=0)
    assert progress.buy_ship(ALLROUNDER) is ShopResult.ALREADY_OWNED


def test_buy_accessory_and_tint() -> None:
    progress = Progress(coins=SHIELD.price + GOLD.price)
    assert progress.buy_accessory(SHIELD) is ShopResult.OK
    assert progress.buy_tint(GOLD) is ShopResult.OK
    assert progress.coins == 0
    assert progress.owns_accessory(SHIELD)
    assert progress.owns_tint(GOLD)
    assert progress.buy_accessory(MAGNET) is ShopResult.TOO_EXPENSIVE
    assert progress.buy_tint(GOLD) is ShopResult.ALREADY_OWNED


def test_buy_accessory_stacks_up_to_the_cap() -> None:
    progress = Progress(coins=3 * SHIELD.price)
    for expected in (1, 2, 3):
        assert progress.buy_accessory(SHIELD) is ShopResult.OK
        assert progress.accessory_count(SHIELD) == expected
    assert progress.coins == 0

    progress.accessory_stock[SHIELD.id] = ACCESSORY_MAX_STOCK
    progress.coins = SHIELD.price
    assert progress.buy_accessory(SHIELD) is ShopResult.STOCK_FULL
    assert progress.coins == SHIELD.price  # volles Lager kostet nichts


def test_add_coins_rejects_negative() -> None:
    progress = Progress()
    progress.add_coins(5)
    assert progress.coins == 5
    with pytest.raises(ValueError):
        progress.add_coins(-1)


# --- Progress: Ausrüsten ----------------------------------------------------------


def test_toggle_accessory_requires_ownership() -> None:
    progress = Progress()
    assert progress.toggle_accessory(ALLROUNDER, SHIELD) is ShopResult.NOT_OWNED
    assert progress.equipped_accessories(ALLROUNDER) == []


def test_toggle_accessory_equips_and_unequips() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 1})
    assert progress.toggle_accessory(ALLROUNDER, SHIELD) is ShopResult.OK
    assert progress.is_equipped(ALLROUNDER, SHIELD)
    assert progress.equipped_accessories(ALLROUNDER) == [SHIELD]
    assert progress.free_slots(ALLROUNDER) == 0

    assert progress.toggle_accessory(ALLROUNDER, SHIELD) is ShopResult.OK
    assert not progress.is_equipped(ALLROUNDER, SHIELD)
    assert progress.equipped == {}


def test_toggle_accessory_respects_ship_slots() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 1, MAGNET.id: 1, ARMOR.id: 1})
    # Allrounder: 1 Platz, Brawler: 2, Racer: 0.
    assert progress.toggle_accessory(ALLROUNDER, SHIELD) is ShopResult.OK
    assert progress.toggle_accessory(ALLROUNDER, MAGNET) is ShopResult.NO_FREE_SLOT
    assert progress.toggle_accessory(BRAWLER, SHIELD) is ShopResult.OK
    assert progress.toggle_accessory(BRAWLER, MAGNET) is ShopResult.OK
    assert progress.toggle_accessory(BRAWLER, ARMOR) is ShopResult.NO_FREE_SLOT
    assert progress.toggle_accessory(RACER, SHIELD) is ShopResult.NO_FREE_SLOT
    assert RACER.name not in progress.equipped


def test_equipment_is_per_ship() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 1})
    progress.toggle_accessory(ALLROUNDER, SHIELD)
    assert not progress.is_equipped(BRAWLER, SHIELD)


# --- Progress: Verbrauch pro Lauf --------------------------------------------------


def test_consume_loadout_uses_one_of_each() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 2, MAGNET.id: 1})
    progress.toggle_accessory(BRAWLER, SHIELD)
    progress.toggle_accessory(BRAWLER, MAGNET)

    assert progress.consume_loadout(BRAWLER) == [SHIELD, MAGNET]
    assert progress.accessory_count(SHIELD) == 1
    assert progress.accessory_count(MAGNET) == 0
    # Schild reicht für den nächsten Lauf und bleibt vorgemerkt, der Magnet nicht.
    assert progress.equipped == {BRAWLER.name: [SHIELD.id]}

    assert progress.consume_loadout(BRAWLER) == [SHIELD]
    assert progress.accessory_stock == {}
    assert progress.equipped == {}


def test_consume_loadout_clears_last_item_on_every_ship() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 1})
    progress.toggle_accessory(ALLROUNDER, SHIELD)
    progress.toggle_accessory(BRAWLER, SHIELD)

    progress.consume_loadout(ALLROUNDER)
    assert progress.equipped == {}
    assert progress.toggle_accessory(BRAWLER, SHIELD) is ShopResult.NOT_OWNED


def test_consume_loadout_without_equipment_is_noop() -> None:
    progress = Progress(accessory_stock={SHIELD.id: 1})
    assert progress.consume_loadout(RACER) == []
    assert progress.accessory_count(SHIELD) == 1


# --- Progress: Farben -------------------------------------------------------------


def test_apply_tint_requires_ownership_and_falls_back_to_default() -> None:
    progress = Progress()
    assert progress.apply_tint(BRAWLER, GOLD) is ShopResult.NOT_OWNED
    assert progress.ship_tint(BRAWLER) == BRAWLER.tint

    progress.owned_tints.add(GOLD.id)
    assert progress.apply_tint(BRAWLER, GOLD) is ShopResult.OK
    assert progress.active_tint(BRAWLER) is GOLD
    assert progress.ship_tint(BRAWLER) == GOLD.color
    # Andere Schiffe behalten ihre Standardfarbe.
    assert progress.ship_tint(ALLROUNDER) is None

    assert progress.apply_tint(BRAWLER, None) is ShopResult.OK
    assert progress.active_tint(BRAWLER) is None
    assert progress.ship_tint(BRAWLER) == BRAWLER.tint


# --- Serialisierung ---------------------------------------------------------------


def _full_progress() -> Progress:
    progress = Progress(coins=42)
    progress.unlocked_ships.add(BRAWLER.name)
    progress.accessory_stock.update({SHIELD.id: 2, MAGNET.id: 1})
    progress.owned_tints.add(GOLD.id)
    progress.toggle_accessory(BRAWLER, SHIELD)
    progress.toggle_accessory(BRAWLER, MAGNET)
    progress.apply_tint(BRAWLER, GOLD)
    return progress


def test_progress_roundtrip() -> None:
    progress = _full_progress()
    restored = Progress.from_dict(json.loads(json.dumps(progress.to_dict())))
    assert restored == progress


def test_from_dict_tolerates_garbage() -> None:
    assert Progress.from_dict(None) == Progress()
    assert Progress.from_dict([1, 2, 3]) == Progress()
    assert Progress.from_dict("nope") == Progress()
    assert Progress.from_dict({}) == Progress()


def test_from_dict_ignores_wrong_types_and_unknown_ids() -> None:
    restored = Progress.from_dict(
        {
            "coins": "viel",
            "unlocked_ships": ["Brawler", "Todesstern", 7],
            "accessory_stock": "shield",
            "owned_tints": ["gold", "neon"],
            "equipped": {"Brawler": ["shield"], "Nope": ["magnet"]},
            "tints": {"Brawler": "gold", "Allrounder": "neon", "Racer": 3},
        }
    )
    assert restored.coins == 0
    assert restored.unlocked_ships == {ALLROUNDER.name, BRAWLER.name}
    assert restored.accessory_stock == {}
    assert restored.owned_tints == {GOLD.id}
    # Schild nicht gekauft -> nicht ausrüstbar, auch wenn die Datei es behauptet.
    assert restored.equipped == {}
    assert restored.tints == {BRAWLER.name: GOLD.id}


def test_from_dict_rejects_bool_and_negative_coins() -> None:
    assert Progress.from_dict({"coins": True}).coins == 0
    assert Progress.from_dict({"coins": -5}).coins == 0
    assert Progress.from_dict({"coins": 12}).coins == 12


def test_from_dict_truncates_equipment_to_slots() -> None:
    restored = Progress.from_dict(
        {
            "owned_accessories": ["shield", "magnet", "armor"],
            "equipped": {"Allrounder": ["shield", "magnet"], "Racer": ["armor"]},
        }
    )
    assert restored.equipped == {ALLROUNDER.name: [SHIELD.id]}


def test_from_dict_migrates_single_purchase_to_one_of_each() -> None:
    # Speicherformat 1: Zubehör war ein Einmalkauf ohne Stückzahl.
    restored = Progress.from_dict(
        {"owned_accessories": ["shield", "magnet"], "equipped": {"Brawler": ["shield"]}}
    )
    assert restored.accessory_stock == {SHIELD.id: 1, MAGNET.id: 1}
    assert restored.equipped == {BRAWLER.name: [SHIELD.id]}


def test_from_dict_cleans_accessory_stock() -> None:
    restored = Progress.from_dict(
        {
            "accessory_stock": {
                "shield": 3,
                "magnet": 0,
                "armor": -2,
                "ammo_reserve": True,
                "phaser": 5,
                7: 1,
            }
        }
    )
    assert restored.accessory_stock == {SHIELD.id: 3}
    assert Progress.from_dict({"accessory_stock": {"shield": 10**6}}).accessory_stock == {
        SHIELD.id: ACCESSORY_MAX_STOCK
    }


def test_from_dict_ignores_duplicate_equipment_ids() -> None:
    restored = Progress.from_dict(
        {"owned_accessories": ["shield"], "equipped": {"Brawler": ["shield", "shield"]}}
    )
    assert restored.equipped == {BRAWLER.name: [SHIELD.id]}


def test_from_dict_always_keeps_free_ships() -> None:
    restored = Progress.from_dict({"unlocked_ships": []})
    assert restored.is_ship_unlocked(ALLROUNDER)


# --- SaveStore ----------------------------------------------------------------------


def test_save_store_missing_file_yields_fresh_progress(tmp_path: Path) -> None:
    store = SaveStore(tmp_path / "nested" / SAVE_FILENAME)
    assert store.load() == Progress()


def test_save_store_roundtrip_creates_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deeper" / SAVE_FILENAME
    store = SaveStore(path)
    progress = _full_progress()
    assert store.save(progress) is True
    assert path.exists()
    assert not path.with_name(path.name + ".tmp").exists()
    assert SaveStore(path).load() == progress


def test_save_store_writes_json_not_pickle(tmp_path: Path) -> None:
    path = tmp_path / SAVE_FILENAME
    SaveStore(path).save(Progress(coins=3))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["coins"] == 3
    assert data["version"] == SAVE_FORMAT_VERSION


def test_save_store_tolerates_broken_file(tmp_path: Path) -> None:
    path = tmp_path / SAVE_FILENAME
    path.write_text("{ kaputt", encoding="utf-8")
    assert SaveStore(path).load() == Progress()
    path.write_bytes(b"\xff\xfe\x00garbage")
    assert SaveStore(path).load() == Progress()


def test_save_store_reports_unwritable_target(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    # Elternpfad ist eine Datei -> mkdir schlägt fehl, save gibt False statt zu werfen.
    store = SaveStore(blocker / SAVE_FILENAME)
    assert store.save(Progress()) is False


def test_default_save_dir_honours_env_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    assert default_save_dir() == tmp_path
    assert default_save_path() == tmp_path / SAVE_FILENAME


def test_default_save_dir_is_user_writable_location(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SAVE_DIR_ENV, raising=False)
    path = default_save_dir()
    assert path.name == "meteorite-dash"
    assert path.is_absolute()
