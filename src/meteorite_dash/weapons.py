from dataclasses import dataclass, replace
from enum import Enum

from meteorite_dash.config import (
    SHOOT_COOLDOWN,
    STANDARD_WEAPON_DAMAGE,
    STANDARD_WEAPON_MAX_AMMO,
    STANDARD_WEAPON_SOUND,
)


class WeaponKind(Enum):
    STANDARD = "standard"


@dataclass(frozen=True)
class WeaponSpec:
    kind: WeaponKind
    name: str
    max_ammo: int
    permanent: bool
    damage: int
    fire_cooldown: float
    sound: str | None = None


STANDARD_WEAPON = WeaponSpec(
    kind=WeaponKind.STANDARD,
    name="Standard",
    max_ammo=STANDARD_WEAPON_MAX_AMMO,
    permanent=True,
    damage=STANDARD_WEAPON_DAMAGE,
    fire_cooldown=SHOOT_COOLDOWN,
    sound=STANDARD_WEAPON_SOUND,
)


@dataclass
class WeaponInstance:
    spec: WeaponSpec
    ammo: int


class WeaponLoadout:
    """Verwaltet die Waffen eines Schiffs.

    Slot 0 ist immer die permanente Standardwaffe. Weitere Slots können später
    einmalige Spezialwaffen aufnehmen; leere Spezialwaffen werden entfernt.
    """

    def __init__(self, weapon_slots: int, *, standard_ammo_bonus: int = 0) -> None:
        if weapon_slots < 1:
            raise ValueError("weapon_slots muss mindestens 1 sein")
        if standard_ammo_bonus < 0:
            raise ValueError("standard_ammo_bonus darf nicht negativ sein")
        self._max_slots = weapon_slots
        # Zubehör "Extra-Munition" vergrößert das Magazin der Standardwaffe.
        standard = STANDARD_WEAPON
        if standard_ammo_bonus:
            standard = replace(standard, max_ammo=standard.max_ammo + standard_ammo_bonus)
        self._weapons: list[WeaponInstance] = [WeaponInstance(standard, standard.max_ammo)]
        self.active_index = 0

    @property
    def max_slots(self) -> int:
        return self._max_slots

    @property
    def weapons(self) -> tuple[WeaponInstance, ...]:
        return tuple(self._weapons)

    @property
    def active(self) -> WeaponInstance:
        return self._weapons[self.active_index]

    def can_fire(self) -> bool:
        return self.active.ammo > 0

    def fire(self) -> bool:
        if not self.can_fire():
            return False
        self.active.ammo -= 1
        if not self.active.spec.permanent and self.active.ammo == 0:
            self._remove_active()
        return True

    def refill_standard(self) -> None:
        for weapon in self._weapons:
            if weapon.spec.permanent:
                weapon.ammo = weapon.spec.max_ammo
                return

    def cycle_weapon(self) -> None:
        if len(self._weapons) <= 1:
            return
        self.active_index = (self.active_index + 1) % len(self._weapons)

    def add_weapon(self, spec: WeaponSpec) -> bool:
        """Fügt eine Spezialwaffe hinzu, wenn noch ein freier Slot existiert."""
        if spec.permanent or len(self._weapons) >= self._max_slots:
            return False
        self._weapons.append(WeaponInstance(spec, spec.max_ammo))
        return True

    def _remove_active(self) -> None:
        if self.active.spec.permanent:
            return
        del self._weapons[self.active_index]
        self.active_index = min(self.active_index, len(self._weapons) - 1)
