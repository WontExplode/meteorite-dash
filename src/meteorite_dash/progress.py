"""Spielfortschritt (Issue #14): Münz-Guthaben, Freischaltungen und Ausrüstung.

`Progress` ist reine Logik ohne Display-Abhängigkeit: Kaufen, Ausrüsten und
Farbwahl liefern ein `ShopResult`, die Szenen übersetzen das in Text. Schiffe
und Farben werden einmal gekauft, Zubehör dagegen auf Vorrat: `accessory_stock`
zählt die Exemplare je Art, `equipped` merkt die Auswahl fürs nächste Schiff und
`consume_loadout` bucht sie beim Laufstart ab.

Die Serialisierung ist defensiv — fehlende oder falsch typisierte Felder fallen
auf Standardwerte zurück, unbekannte Katalog-IDs werden verworfen.
"""

from collections.abc import Container
from dataclasses import dataclass, field
from enum import Enum, auto

from meteorite_dash.accessories import ACCESSORIES_BY_ID, AccessorySpec
from meteorite_dash.config import ACCESSORY_MAX_STOCK, SAVE_FORMAT_VERSION, Color
from meteorite_dash.ships import SHIPS, SHIPS_BY_NAME, TINTS_BY_ID, ShipSpec, TintSpec


class ShopResult(Enum):
    """Ergebnis einer Shop-Aktion; die Szene übersetzt es in Text."""

    OK = auto()
    ALREADY_OWNED = auto()
    TOO_EXPENSIVE = auto()
    NOT_OWNED = auto()
    NO_FREE_SLOT = auto()
    STOCK_FULL = auto()


def _free_ships() -> set[str]:
    """Namen aller Schiffe mit `price == 0` — von Anfang an freigeschaltet."""
    return {spec.name for spec in SHIPS if spec.is_free}


@dataclass
class Progress:
    """Persistenter Spielfortschritt: Guthaben, Freischaltungen und Ausrüstung.

    Farben werden einmal gekauft und pro Schiff gewählt; Zubehör liegt als
    Vorrat im Lager und wird pro Lauf verbraucht. `equipped` und `tints` sind
    nach Schiffsnamen abgelegt.
    """

    coins: int = 0
    unlocked_ships: set[str] = field(default_factory=_free_ships)
    # Zubehör-ID -> Exemplare im Lager; ein Lauf verbraucht die eingesetzten.
    accessory_stock: dict[str, int] = field(default_factory=dict)
    owned_tints: set[str] = field(default_factory=set)
    # Schiffsname -> ausgerüstete Zubehör-IDs (Reihenfolge = Slot-Reihenfolge).
    equipped: dict[str, list[str]] = field(default_factory=dict)
    # Schiffsname -> Farb-ID; fehlt der Eintrag, gilt `ShipSpec.tint`.
    tints: dict[str, str] = field(default_factory=dict)

    # --- Abfragen -------------------------------------------------------------

    def can_afford(self, price: int) -> bool:
        """True, wenn das Guthaben `price` deckt."""
        return self.coins >= price

    def is_ship_unlocked(self, spec: ShipSpec) -> bool:
        """Kostenlose Schiffe sind immer frei, sonst zählt `unlocked_ships`."""
        return spec.is_free or spec.name in self.unlocked_ships

    def accessory_count(self, spec: AccessorySpec) -> int:
        """Exemplare von `spec` im Lager."""
        return self.accessory_stock.get(spec.id, 0)

    def owns_accessory(self, spec: AccessorySpec) -> bool:
        """True, wenn mindestens ein Exemplar im Lager liegt."""
        return self.accessory_count(spec) > 0

    def owns_tint(self, spec: TintSpec) -> bool:
        """True, wenn die Farbe gekauft ist."""
        return spec.id in self.owned_tints

    def equipped_accessories(self, ship: ShipSpec) -> list[AccessorySpec]:
        """Für den nächsten Lauf eingeplantes Zubehör von `ship` in Slot-Reihenfolge."""
        return [ACCESSORIES_BY_ID[acc_id] for acc_id in self.equipped.get(ship.name, [])]

    def is_equipped(self, ship: ShipSpec, spec: AccessorySpec) -> bool:
        """True, wenn `spec` auf `ship` liegt."""
        return spec.id in self.equipped.get(ship.name, [])

    def free_slots(self, ship: ShipSpec) -> int:
        """Noch freie Zubehör-Slots von `ship`."""
        return ship.accessory_slots - len(self.equipped.get(ship.name, []))

    def active_tint(self, ship: ShipSpec) -> TintSpec | None:
        """Gewählte Kauf-Farbe von `ship`; `None` heißt Standardfarbe."""
        tint_id = self.tints.get(ship.name)
        return TINTS_BY_ID[tint_id] if tint_id is not None else None

    def ship_tint(self, ship: ShipSpec) -> Color | None:
        """Effektive Färbung: gekaufte Farbe, sonst Standardfarbe des Schiffs."""
        tint = self.active_tint(ship)
        return tint.color if tint is not None else ship.tint

    # --- Aktionen -------------------------------------------------------------

    def add_coins(self, amount: int) -> None:
        """Schreibt Münzen gut; ein negativer Betrag ist ein Programmierfehler."""
        if amount < 0:
            raise ValueError("amount darf nicht negativ sein")
        self.coins += amount

    def _pay(self, price: int) -> ShopResult:
        """Zieht `price` ab, wenn bezahlbar; sonst `TOO_EXPENSIVE` ohne Abzug."""
        if not self.can_afford(price):
            return ShopResult.TOO_EXPENSIVE
        self.coins -= price
        return ShopResult.OK

    def buy_ship(self, spec: ShipSpec) -> ShopResult:
        """Schaltet `spec` gegen Münzen frei."""
        if self.is_ship_unlocked(spec):
            return ShopResult.ALREADY_OWNED
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.unlocked_ships.add(spec.name)
        return result

    def buy_accessory(self, spec: AccessorySpec) -> ShopResult:
        """Legt ein weiteres Exemplar von `spec` ins Lager (Verbrauchsware).

        Wiederholt kaufbar bis `ACCESSORY_MAX_STOCK`; ausgewählt wird vor dem
        Lauf über `toggle_accessory`.
        """
        if self.accessory_count(spec) >= ACCESSORY_MAX_STOCK:
            return ShopResult.STOCK_FULL
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.accessory_stock[spec.id] = self.accessory_count(spec) + 1
        return result

    def buy_tint(self, spec: TintSpec) -> ShopResult:
        """Kauft `spec` einmalig; die Wahl pro Schiff läuft über `apply_tint`."""
        if self.owns_tint(spec):
            return ShopResult.ALREADY_OWNED
        result = self._pay(spec.price)
        if result is ShopResult.OK:
            self.owned_tints.add(spec.id)
        return result

    def toggle_accessory(self, ship: ShipSpec, spec: AccessorySpec) -> ShopResult:
        """Legt vorrätiges Zubehör auf einen Platz von `ship` bzw. nimmt es herunter."""
        slots = list(self.equipped.get(ship.name, []))
        if spec.id in slots:
            slots.remove(spec.id)
        elif not self.owns_accessory(spec):
            return ShopResult.NOT_OWNED
        elif len(slots) >= ship.accessory_slots:
            return ShopResult.NO_FREE_SLOT
        else:
            slots.append(spec.id)
        self._set_slots(ship.name, slots)
        return ShopResult.OK

    def consume_loadout(self, ship: ShipSpec) -> list[AccessorySpec]:
        """Bucht das Zubehör von `ship` ab — ein Exemplar hält einen Lauf.

        Liefert die eingesetzten Teile in Slot-Reihenfolge. Was danach nicht mehr
        im Lager liegt, fällt von den Plätzen **aller** Schiffe; der Rest bleibt
        vorgemerkt, damit der nächste Lauf ohne Umweg startet.
        """
        used = self.equipped_accessories(ship)
        for spec in used:
            remaining = self.accessory_count(spec) - 1
            if remaining > 0:
                self.accessory_stock[spec.id] = remaining
            else:
                self.accessory_stock.pop(spec.id, None)
                self._unequip_everywhere(spec)
        return used

    def apply_tint(self, ship: ShipSpec, spec: TintSpec | None) -> ShopResult:
        """Setzt die Farbe von `ship`; `None` stellt die Standardfarbe wieder her."""
        if spec is None:
            self.tints.pop(ship.name, None)
            return ShopResult.OK
        if not self.owns_tint(spec):
            return ShopResult.NOT_OWNED
        self.tints[ship.name] = spec.id
        return ShopResult.OK

    def _set_slots(self, ship_name: str, slots: list[str]) -> None:
        """Schreibt die Platzbelegung; eine leere Belegung wird ganz entfernt."""
        if slots:
            self.equipped[ship_name] = slots
        else:
            self.equipped.pop(ship_name, None)

    def _unequip_everywhere(self, spec: AccessorySpec) -> None:
        """Nimmt `spec` von den Plätzen aller Schiffe — der Vorrat ist alle."""
        for ship_name, ids in list(self.equipped.items()):
            if spec.id in ids:
                self._set_slots(ship_name, [acc_id for acc_id in ids if acc_id != spec.id])

    # --- Serialisierung -------------------------------------------------------

    def to_dict(self) -> dict[str, object]:
        """JSON-taugliche Darstellung mit sortierten Sammlungen (stabile Ausgabe)."""
        return {
            "version": SAVE_FORMAT_VERSION,
            "coins": self.coins,
            "unlocked_ships": sorted(self.unlocked_ships),
            "accessory_stock": dict(sorted(self.accessory_stock.items())),
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
        progress.accessory_stock = _accessory_stock(data)
        progress.owned_tints = _known_ids(data.get("owned_tints"), TINTS_BY_ID)

        equipped = data.get("equipped")
        if isinstance(equipped, dict):
            for ship_name, ids in equipped.items():
                ship = SHIPS_BY_NAME.get(ship_name) if isinstance(ship_name, str) else None
                if ship is None or not isinstance(ids, list):
                    continue
                for acc_id in ids:
                    if not isinstance(acc_id, str) or acc_id not in progress.accessory_stock:
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
    """Nicht-negativer `int` (kein `bool`), sonst 0."""
    # bool ist Unterklasse von int — `True` als Guthaben wäre Unsinn.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _known_ids(value: object, catalog: Container[str]) -> set[str]:
    """Die Strings aus `value`, die im `catalog` bekannt sind; alles andere fällt weg."""
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str) and item in catalog}


def _accessory_stock(data: dict[str, object]) -> dict[str, int]:
    """Zubehör-Vorrat aus dem Speicherstand, gedeckelt auf `ACCESSORY_MAX_STOCK`.

    Vor Speicherformat 2 war Zubehör ein Einmalkauf (`owned_accessories`); jedes
    gekaufte Teil zählt dann als genau ein Exemplar.
    """
    raw = data.get("accessory_stock")
    if raw is None:
        return dict.fromkeys(_known_ids(data.get("owned_accessories"), ACCESSORIES_BY_ID), 1)
    if not isinstance(raw, dict):
        return {}
    stock: dict[str, int] = {}
    for acc_id, count in raw.items():
        if not isinstance(acc_id, str) or acc_id not in ACCESSORIES_BY_ID:
            continue
        amount = min(_non_negative_int(count), ACCESSORY_MAX_STOCK)
        if amount > 0:
            stock[acc_id] = amount
    return stock
