"""Pixelgenaue Hitboxen: Masken, Formen und die Kollision darüber."""

import pygame

from meteorite_dash.coins import Coin, CoinFormation, Pickup
from meteorite_dash.config import (
    AMMO_PICKUP_SIZE,
    COIN_RADIUS,
    ENEMY_SIZE,
    METEORITE_VARIANTS,
    PLAYER_SIZE,
)
from meteorite_dash.entities import AmmoPickup, Meteorite, WaveEnemy, collect_pickups
from meteorite_dash.hitbox import (
    circle_mask,
    image_mask,
    left_triangle_mask,
    overlaps,
    ship_mask,
    solid,
    solid_mask,
)
from meteorite_dash.player import Player
from meteorite_dash.projectiles import Projectile
from meteorite_dash.ships import SHIPS


def _large_meteorite(topleft: tuple[int, int]) -> Meteorite:
    variant = METEORITE_VARIANTS[-1]
    diameter = variant.radius * 2
    return Meteorite(
        pygame.Rect(*topleft, diameter, diameter),
        0.0,
        variant.images[0],
        hp=variant.hp,
        contact_damage=variant.contact_damage,
    )


def test_masks_match_their_rect_size() -> None:
    player = Player((50, 100), SHIPS[0])
    meteorite = _large_meteorite((0, 0))
    enemy = WaveEnemy(pygame.Rect(0, 0, *ENEMY_SIZE), 0.0)
    pickup = AmmoPickup(pygame.Rect(0, 0, *AMMO_PICKUP_SIZE), 0.0)
    coin = Coin(pygame.Rect(0, 0, COIN_RADIUS * 2, COIN_RADIUS * 2), 0.0)
    projectile = Projectile(pygame.Rect(0, 0, 16, 8), 0.0, damage=10)
    for item in (player, meteorite, enemy, pickup, coin, projectile):
        assert item.mask.get_size() == item.rect.size


def test_sprite_masks_are_smaller_than_their_box() -> None:
    """Genau hier lag der Bug: Schiff und Meteorit füllen ihr Rechteck nicht."""
    player = Player((50, 100), SHIPS[0])
    meteorite = _large_meteorite((0, 0))
    assert 0 < player.mask.count() < PLAYER_SIZE[0] * PLAYER_SIZE[1]
    assert 0 < meteorite.mask.count() < meteorite.rect.width * meteorite.rect.height


def test_touching_boxes_without_touching_pixels_do_not_collide() -> None:
    player = Player((50, 100), SHIPS[0])
    meteorite = _large_meteorite((player.rect.right - 6, player.rect.bottom - 6))
    assert player.rect.colliderect(meteorite.rect) is True
    assert overlaps(player, meteorite) is False

    meteorite.rect.center = player.rect.center
    assert overlaps(player, meteorite) is True


def test_shapes_follow_what_is_drawn() -> None:
    triangle = left_triangle_mask((44, 44))
    assert triangle.get_at((0, 22)) == 1  # Spitze links
    assert triangle.get_at((0, 0)) == 0  # Ecke oben links ist Luft
    circle = circle_mask((24, 24))
    assert circle.get_at((12, 12)) == 1
    assert circle.get_at((0, 0)) == 0
    assert solid_mask((8, 4)).count() == 32


def test_masks_are_cached_per_key() -> None:
    """Masken werden einmal gebaut — sonst kostet jede Kollision Bildarbeit."""
    assert ship_mask(SHIPS[0].sprite, PLAYER_SIZE) is ship_mask(SHIPS[0].sprite, PLAYER_SIZE)
    name = METEORITE_VARIANTS[0].images[0]
    assert image_mask(name, (40, 40)) is image_mask(name, (40, 40))
    assert image_mask(name, (40, 40)) is not image_mask(name, (60, 60))


def test_pickups_and_coins_use_pixel_collision() -> None:
    player = Player((50, 100), SHIPS[0])
    # Diagonal an der Ecke: die Boxen überlappen, die Silhouetten nicht.
    corner = (player.rect.right - 4, player.rect.bottom - 4)
    pickup = AmmoPickup(pygame.Rect(*corner, *AMMO_PICKUP_SIZE), 0.0)
    entities: list[AmmoPickup] = [pickup]
    assert collect_pickups(player, list(entities)) == []

    coin = Coin(pygame.Rect(*corner, COIN_RADIUS * 2, COIN_RADIUS * 2), 0.0)
    formation = CoinFormation([coin], bonus=5)
    assert formation.collect(player) == Pickup(0, 0)
    coin.rect.center = player.rect.center
    assert formation.collect(player) == Pickup(1, 5)


def test_solid_box_behaves_like_a_rectangle() -> None:
    box = solid(pygame.Rect(0, 0, 20, 20))
    assert box.mask.count() == 400
    assert overlaps(box, solid(pygame.Rect(19, 19, 5, 5))) is True
    assert overlaps(box, solid(pygame.Rect(20, 20, 5, 5))) is False
