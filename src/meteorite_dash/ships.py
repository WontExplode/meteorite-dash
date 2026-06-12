from dataclasses import dataclass

from meteorite_dash.config import DRAG, Color


@dataclass(frozen=True)
class ShipSpec:
    """Physikalisches Datenblatt eines Schiffs.

    Spielwerte (Beschleunigung, Endgeschwindigkeit, Wendigkeit, HP) werden aus
    den Grundwerten abgeleitet, statt einzeln gepflegt zu werden. Das
    Physikmodell ist ein linearer Widerstand: F = direction * thrust - DRAG * v.
    """

    name: str
    sprite: str
    tint: Color | None
    mass: float
    thrust: float
    hull: float
    weapon_slots: int
    accessory_slots: int

    def __post_init__(self) -> None:
        if self.mass <= 0 or self.thrust <= 0 or self.hull <= 0:
            raise ValueError(f"{self.name}: mass, thrust und hull müssen > 0 sein")
        if self.weapon_slots < 0 or self.accessory_slots < 0:
            raise ValueError(f"{self.name}: Slots dürfen nicht negativ sein")

    @property
    def acceleration(self) -> float:
        """Anzugsverhalten in px/s² (F = m * a)."""
        return self.thrust / self.mass

    @property
    def max_speed(self) -> float:
        """Endgeschwindigkeit in px/s, bei der Schub und Widerstand sich aufheben."""
        return self.thrust / DRAG

    @property
    def agility(self) -> float:
        """Wie schnell das Schiff stoppt und umlenkt; der Kehrwert ist der Drift."""
        return DRAG / self.mass

    @property
    def hp(self) -> int:
        """Lebenspunkte; Schadenslogik folgt mit den Meteoriten."""
        return round(self.hull)


# Ein neues Schiff = ein neuer Eintrag. Tints sind Platzhalter-Farbvarianten,
# bis eigene Grafiken vorliegen.
SHIPS: tuple[ShipSpec, ...] = (
    ShipSpec(
        name="Allrounder",
        sprite="CopperShip1.png",
        tint=None,
        mass=1.0,
        thrust=1200.0,
        hull=100.0,
        weapon_slots=2,
        accessory_slots=1,
    ),
    ShipSpec(
        name="Interceptor",
        sprite="CopperShip1.png",
        tint=(120, 180, 255),
        mass=0.5,
        thrust=1120.0,
        hull=60.0,
        weapon_slots=1,
        accessory_slots=1,
    ),
    ShipSpec(
        name="Brawler",
        sprite="CopperShip3.png",
        tint=(255, 110, 90),
        mass=2.6,
        thrust=960.0,
        hull=200.0,
        weapon_slots=3,
        accessory_slots=2,
    ),
    ShipSpec(
        name="Racer",
        sprite="CopperShip3.png",
        tint=(140, 255, 160),
        mass=2.0,
        thrust=1680.0,
        hull=80.0,
        weapon_slots=1,
        accessory_slots=0,
    ),
)
