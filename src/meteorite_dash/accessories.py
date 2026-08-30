"""Zubehör-Katalog (Issue #14): kaufbare Ausrüstung für die `ShipSpec.accessory_slots`.

Ein Zubehör wird einmal gekauft und kann danach auf jedem Schiff mit freiem
Platz ausgerüstet werden. Die Effekte selbst wendet `Simulation.__init__` aus
der `RunConfig` an; die Stärke der Effekte steht in `config.py`.
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
    """Katalog-Eintrag eines Zubehörs: Art, Anzeigename, Beschreibung und Preis."""

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


ACCESSORIES: tuple[AccessorySpec, ...] = (
    AccessorySpec(
        AccessoryKind.SHIELD,
        "Schild",
        f"Blockt {SHIELD_CHARGES} Kollision pro Lauf ohne Schaden",
        250,
    ),
    AccessorySpec(
        AccessoryKind.MAGNET,
        "Magnet",
        "Zieht Münzen in der Nähe zum Schiff",
        200,
    ),
    AccessorySpec(
        AccessoryKind.AMMO_RESERVE,
        "Extra-Munition",
        f"+{AMMO_RESERVE_BONUS} Schuss im Standard-Magazin",
        150,
    ),
    AccessorySpec(
        AccessoryKind.ARMOR,
        "Panzerung",
        f"+{ARMOR_HP_BONUS} Hülle",
        300,
    ),
)
ACCESSORIES_BY_ID: dict[str, AccessorySpec] = {spec.id: spec for spec in ACCESSORIES}
