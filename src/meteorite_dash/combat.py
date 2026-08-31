"""Kampflogik: Projektiltreffer und Kollisionsschaden, rein logisch und headless testbar.

Alle Berührungen laufen pixelgenau über `hitbox.overlaps` — der Rechteck-Test
ist nur noch die schnelle Vorauswahl darin.
"""

from typing import NamedTuple, Protocol, runtime_checkable

from meteorite_dash.entities import DamageableEntity, Entity
from meteorite_dash.hitbox import HasHitbox, overlaps
from meteorite_dash.projectiles import Projectile


@runtime_checkable
class Damageable(Protocol):
    """Alles, was Projektile treffen können: HP, Kontaktschaden, `take_damage`."""

    hp: int
    contact_damage: int

    def take_damage(self, amount: int) -> bool:
        """Wendet Schaden an. Gibt True zurück, wenn das Ziel zerstört wurde."""


class Impact(NamedTuple):
    """Ein Projektiltreffer: Aufschlagpunkt (Referenzraum) und ob das Ziel zerbrach.

    Rein beschreibend — die `Simulation` macht daraus `HIT`/`DESTROYED`-Events,
    die Szene daraus Funken und Explosionen.
    """

    position: tuple[int, int]
    destroyed: bool


def resolve_projectile_hits(projectiles: list[Projectile], entities: list[Entity]) -> list[Impact]:
    """Entfernt getroffene Projektile und zerstörte Gegner; liefert die Treffer."""
    spent_projectiles: set[int] = set()
    destroyed_entities: set[int] = set()
    impacts: list[Impact] = []

    for projectile_index, projectile in enumerate(projectiles):
        for entity_index, entity in enumerate(entities):
            if entity_index in destroyed_entities:
                continue
            if not isinstance(entity, Damageable):
                continue
            if not overlaps(projectile, entity):
                continue
            destroyed = entity.take_damage(projectile.damage)
            if destroyed:
                destroyed_entities.add(entity_index)
            spent_projectiles.add(projectile_index)
            impacts.append(Impact(projectile.rect.clip(entity.rect).center, destroyed))
            break

    if spent_projectiles:
        projectiles[:] = [
            projectile
            for index, projectile in enumerate(projectiles)
            if index not in spent_projectiles
        ]
    if destroyed_entities:
        entities[:] = [
            entity for index, entity in enumerate(entities) if index not in destroyed_entities
        ]
    return impacts


def _split_contact_hits(
    player: HasHitbox, entities: list[Entity]
) -> tuple[list[DamageableEntity], list[Entity]]:
    """Teilt in Gefahren, die den Spieler gerade berühren, und alle übrigen."""
    hits: list[DamageableEntity] = []
    remaining: list[Entity] = []
    for entity in entities:
        if (
            entity.damages_player
            and isinstance(entity, DamageableEntity)
            and overlaps(player, entity)
        ):
            hits.append(entity)
        else:
            remaining.append(entity)
    return hits, remaining


def apply_contact_damage(player: HasHitbox, hp: int, entities: list[Entity]) -> int:
    """Wendet Kollisionsschaden auf den Spieler an und entfernt getroffene Gegner."""
    if hp <= 0:
        return hp

    hits, remaining = _split_contact_hits(player, entities)
    entities[:] = remaining
    return max(0, hp - sum(hit.contact_damage for hit in hits))


def absorb_contact(player: HasHitbox, entities: list[Entity]) -> bool:
    """Schild: entfernt berührende Gefahren ohne Schaden. True, wenn etwas geblockt wurde."""
    hits, remaining = _split_contact_hits(player, entities)
    if not hits:
        return False
    entities[:] = remaining
    return True
