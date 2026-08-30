"""Spielfortschritt (Issue #14): Münz-Guthaben, Freischaltungen und Ausrüstung.

`Progress` ist reine Logik ohne Display-Abhängigkeit: Kaufen, Ausrüsten und
Farbwahl liefern ein `ShopResult`, die Szenen übersetzen das in Text. Die
Serialisierung ist defensiv — fehlende oder falsch typisierte Felder fallen auf
Standardwerte zurück, unbekannte Katalog-IDs werden verworfen.
"""

from collections.abc import Container
from dataclasses import dataclass, field
from enum import Enum, auto

from meteorite_dash.accessories import ACCESSORIES_BY_ID, AccessorySpec
from meteorite_dash.config import SAVE_FORMAT_VERSION, Color
from meteorite_dash.ships import SHIPS, SHIPS_BY_NAME, TINTS_BY_ID, ShipSpec, TintSpec


class ShopResult(Enum):
    OK = auto()
    ALREADY_OWNED = auto()
    TOO_EXPENSIVE = auto()
    NOT_OWNED = auto()
    NO_FREE_SLOT = auto()


def _free_ships() -> set[str]:
    return {spec.name for spec in SHIPS if spec.is_free}


@dataclass
class Progress:
    coins: int = 0
    unlocked_ships: set[str] = field(default_factory=_free_ships)
    owned_accessories: set[str] = field(default_factory=set)
    owned_tints: set[str] = field(default_factory=set)
    # Schiffsname -> ausgerüstete Zubehör-IDs (Reihenfolge = Slot-Reihenfolge).
    equipped: dict[str, list[str]] = field(default_factory=dict)
    # Schiffsname -> Farb-ID; fehlt der Eintrag, gilt `ShipSpec.tint`.
    tints: dict[str, str] = field(default_factory=dict)

    # --- Abfragen -------------------------------------------------------------

    def can_afford(self, price: int) -> bool:
        return self.coins >= price

    def is_ship_unlocked(self, spec: ShipSpec) -> bool:
        return spec.is_free or spec.name in self.unlocked_ships

    def owns_accessory(self, spec: AccessorySpec) -> bool:
        return spec.id in self.owned_accessories

    def owns_tint(self, spec: TintSpec) -> bool:
        return spec.id in self.owned_tints

    def equipped_accessories(self, ship: ShipSpec) -> list[AccessorySpec]:
        return [ACCESSORIES_BY_ID[acc_id] for acc_id in self.equipped.get(ship.name, [])]

    def is_equipped(self, ship: ShipSpec, spec: AccessorySpec) -> bool:
        return spec.id in self.equipped.get(ship.name, [])

    def free_slots(self, ship: ShipSpec) -> int:
        return ship.accessory_slots - len(self.equipped.get(ship.name, []))

    def active_tint(self, ship: ShipSpec) -> TintSpec | None:
        tint_id = self.tints.get(ship.name)
        return TINTS_BY_ID[tint_id] if tint_id is not None else None

    def ship_tint(self, ship: ShipSpec) -> Color | None:
        """Effektive Färbung: gekaufte Farbe, sonst Standardfarbe des Schiffs."""
        tint = self.active_tint(ship)
        return tint.color if tint is not None else ship.tint

    # --- Aktionen -------------------------------------------------------------

    def add_coins(self, amount: int) -> None:
        if amount < 0:
            raise ValueError("amount darf nicht negativ sein")
        self.coins += amount

    def _pay(self, price: int) -> ShopResult:
        if not self.can_afford(price):
            return ShopResult.TOO_EXPENSIVE
        self.coins -= price
        return ShopResult.OK

    def buy_ship(self, spec: ShipSpec) -> ShopResult:
        if self.is_ship_unlocked(spec):
            return ShopResult.ALREADY_OWNED
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.unlocked_ships.add(spec.name)
        return result

    def buy_accessory(self, spec: AccessorySpec) -> ShopResult:
        if self.owns_accessory(spec):
            return ShopResult.ALREADY_OWNED
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.owned_accessories.add(spec.id)
        return result

    def buy_tint(self, spec: TintSpec) -> ShopResult:
        if self.owns_tint(spec):
            return ShopResult.ALREADY_OWNED
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.owned_tints.add(spec.id)
        return result

    def toggle_accessory(self, ship: ShipSpec, spec: AccessorySpec) -> ShopResult:
        """Rüstet gekauftes Zubehör auf `ship` aus bzw. legt es wieder ab."""
        if not self.owns_accessory(spec):
            return ShopResult.NOT_OWNED
        slots = list(self.equipped.get(ship.name, []))
        if spec.id in slots:
            slots.remove(spec.id)
        elif len(slots) >= ship.accessory_slots:
            return ShopResult.NO_FREE_SLOT
        else:
            slots.append(spec.id)
        if slots:
            self.equipped[ship.name] = slots
        else:
            self.equipped.pop(ship.name, None)
        return ShopResult.OK

    def apply_tint(self, ship: ShipSpec, spec: TintSpec | None) -> ShopResult:
        """Setzt die Farbe von `ship`; `None` stellt die Standardfarbe wieder her."""
        if spec is None:
            self.tints.pop(ship.name, None)
            return ShopResult.OK
        if not self.owns_tint(spec):
            return ShopResult.NOT_OWNED
        self.tints[ship.name] = spec.id
        return ShopResult.OK

    # --- Serialisierung -------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        return {
            "version": SAVE_FORMAT_VERSION,
            "coins": self.coins,
            "unlocked_ships": sorted(self.unlocked_ships),
            "owned_accessories": sorted(self.owned_accessories),
            "owned_tints": sorted(self.owned_tints),
            "equipped": {ship: list(ids) for ship, ids in sorted(self.equipped.items())},
            "tints": dict(sorted(self.tints.items())),
        }

    @classmethod
    def from_dict(cls, data: object) -> "Progress":
        """Baut einen Fortschritt aus nicht vertrauenswürdigen Daten (JSON).

        Jedes Feld wird einzeln geprüft; kaputte Teile fallen auf den Standard
        zurück, statt den Ladevorgang abzubrechen.
        """
        if not isinstance(data, dict):
            return cls()
        progress = cls(coins=_non_negative_int(data.get("coins")))
        progress.unlocked_ships |= _known_ids(data.get("unlocked_ships"), SHIPS_BY_NAME)
        progress.owned_accessories = _known_ids(data.get("owned_accessories"), ACCESSORIES_BY_ID)
        progress.owned_tints = _known_ids(data.get("owned_tints"), TINTS_BY_ID)

        equipped = data.get("equipped")
        if isinstance(equipped, dict):
            for ship_name, ids in equipped.items():
                ship = SHIPS_BY_NAME.get(ship_name) if isinstance(ship_name, str) else None
                if ship is None or not isinstance(ids, list):
                    continue
                for acc_id in ids:
                    if not isinstance(acc_id, str) or acc_id not in progress.owned_accessories:
                        continue
                    spec = ACCESSORIES_BY_ID[acc_id]
                    # Doppelte IDs in der Datei dürfen das Toggle nicht wieder ablegen.
                    if not progress.is_equipped(ship, spec):
                        progress.toggle_accessory(ship, spec)

        tints = data.get("tints")
        if isinstance(tints, dict):
            for ship_name, tint_id in tints.items():
                ship = SHIPS_BY_NAME.get(ship_name) if isinstance(ship_name, str) else None
                if ship is None or not isinstance(tint_id, str):
                    continue
                if tint_id in progress.owned_tints:
                    progress.apply_tint(ship, TINTS_BY_ID[tint_id])
        return progress


def _non_negative_int(value: object) -> int:
    # bool ist Unterklasse von int — `True` als Guthaben wäre Unsinn.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _known_ids(value: object, catalog: Container[str]) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item in catalog}
