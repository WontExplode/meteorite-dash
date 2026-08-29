from typing import Protocol, runtime_checkable

import pygame

from meteorite_dash.entities import DamageableEntity, Entity
from meteorite_dash.projectiles import Projectile


@runtime_checkable
class Damageable(Protocol):
    hp: int
    contact_damage: int

    def take_damage(self, amount: int) -> bool:
        """Wendet Schaden an. Gibt True zurück, wenn das Ziel zerstört wurde."""


def resolve_projectile_hits(projectiles: list[Projectile], entities: list[Entity]) -> None:
    """Entfernt getroffene Projektile und zerstörte Gegner/Hindernisse."""
    spent_projectiles: set[int] = set()
    destroyed_entities: set[int] = set()

    for projectile_index, projectile in enumerate(projectiles):
        for entity_index, entity in enumerate(entities):
            if entity_index in destroyed_entities:
                continue
            if not isinstance(entity, Damageable):
                continue
            if not projectile.rect.colliderect(entity.rect):
                continue
            if entity.take_damage(projectile.damage):
                destroyed_entities.add(entity_index)
            spent_projectiles.add(projectile_index)
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


def _split_contact_hits(
    player_rect: pygame.Rect, entities: list[Entity]
) -> tuple[list[DamageableEntity], list[Entity]]:
    """Teilt in Gefahren, die den Spieler gerade berühren, und alle übrigen."""
    hits: list[DamageableEntity] = []
    remaining: list[Entity] = []
    for entity in entities:
        if (
            entity.damages_player
            and isinstance(entity, DamageableEntity)
            and player_rect.colliderect(entity.rect)
        ):
            hits.append(entity)
        else:
            remaining.append(entity)
    return hits, remaining


def apply_contact_damage(player_rect: pygame.Rect, hp: int, entities: list[Entity]) -> int:
    """Wendet Kollisionsschaden auf den Spieler an und entfernt getroffene Gegner."""
    if hp <= 0:
        return hp

    hits, remaining = _split_contact_hits(player_rect, entities)
    entities[:] = remaining
    return max(0, hp - sum(hit.contact_damage for hit in hits))


def absorb_contact(player_rect: pygame.Rect, entities: list[Entity]) -> bool:
    """Schild: entfernt berührende Gefahren ohne Schaden. True, wenn etwas geblockt wurde."""
    hits, remaining = _split_contact_hits(player_rect, entities)
    if not hits:
        return False
    entities[:] = remaining
    return True
