"""Zubehör-Katalog (Issue #14): Verbrauchsware für die `ShipSpec.accessory_slots`.

Zubehör wird auf Vorrat gekauft (`Progress.accessory_stock`) und vor dem Lauf
in der `LoadoutScene` auf die Plätze des Schiffs gelegt. Ein Lauf verbraucht die
eingesetzten Teile — deshalb bleiben Münzen dauerhaft nützlich. Die Effekte
selbst wendet `Simulation.__init__` aus der `RunConfig` an; ihre Stärke steht in
`config.py`.
"""

from dataclasses import dataclass
from enum import Enum

from meteorite_dash.config import AMMO_RESERVE_BONUS, ARMOR_HP_BONUS, SHIELD_CHARGES


class AccessoryKind(Enum):
    """Zubehör-Arten; der Wert ist zugleich die persistente ID."""

    SHIELD = "shield"
    MAGNET = "magnet"
    AMMO_RESERVE = "ammo_reserve"
    ARMOR = "armor"


@dataclass(frozen=True)
class AccessorySpec:
    """Katalog-Eintrag eines Zubehörs: Art, Anzeigename, Beschreibung und Preis.

    Der Preis gilt pro Exemplar; ein Exemplar hält genau einen Lauf.
    """

    kind: AccessoryKind
    name: str
    description: str
    price: int

    def __post_init__(self) -> None:
        if self.price < 0:
            raise ValueError(f"{self.name}: price darf nicht negativ sein")

    @property
    def id(self) -> str:
        """Persistente ID (der `AccessoryKind`-Wert)."""
        return self.kind.value


# Preise sind auf Verbrauch je Lauf gerechnet: ein ordentlicher Lauf bringt
# gut hundert Münzen, ein voll bestücktes Schiff kostet ungefähr so viel.
ACCESSORIES: tuple[AccessorySpec, ...] = (
    AccessorySpec(
        AccessoryKind.SHIELD,
        "Schild",
        f"Blockt {SHIELD_CHARGES} Kollision ohne Schaden",
        80,
    ),
    AccessorySpec(
        AccessoryKind.MAGNET,
        "Magnet",
        "Zieht Münzen in der Nähe zum Schiff",
        60,
    ),
    AccessorySpec(
        AccessoryKind.AMMO_RESERVE,
        "Extra-Munition",
        f"+{AMMO_RESERVE_BONUS} Schuss im Standard-Magazin",
        40,
    ),
    AccessorySpec(
        AccessoryKind.ARMOR,
        "Panzerung",
        f"+{ARMOR_HP_BONUS} Hülle",
        100,
    ),
)
ACCESSORIES_BY_ID: dict[str, AccessorySpec] = {spec.id: spec for spec in ACCESSORIES}
