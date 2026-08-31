import random

import pygame
import pytest

from meteorite_dash.assets import SHIP_IMAGES, AssetLoader, ship_image_path
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.combat import apply_contact_damage, resolve_projectile_hits
from meteorite_dash.config import (
    AMMO_PICKUP_SIZE,
    DEATH_DELAY_SECONDS,
    DRAG,
    GAME_MUSIC_TRACKS,
    MENU_ITEMS,
    METEORITE_COLOR,
    METEORITE_VARIANTS,
    SHOOT_COOLDOWN,
    STANDARD_WEAPON_DAMAGE,
)
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.entities import (
    AmmoPickup,
    Entity,
    HunterEnemy,
    Meteorite,
    WaveEnemy,
    collect_pickups,
    collides_with_any,
    spawn_ammo_pickup,
    spawn_meteorite,
)
from meteorite_dash.hitbox import solid
from meteorite_dash.inputs import InputFrame, from_pressed
from meteorite_dash.player import Player
from meteorite_dash.projectiles import Projectile, spawn_projectile
from meteorite_dash.render import RenderContext
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.scenes.ship_selection import ShipSelection
from meteorite_dash.score import DistanceScore, format_light_years
from meteorite_dash.ships import SHIPS, ShipSpec
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.viewport import Viewport
from meteorite_dash.weapons import STANDARD_WEAPON, WeaponKind, WeaponLoadout, WeaponSpec


class FakeKeys:
    def __init__(self, pressed: set[int]) -> None:
        self._pressed = pressed

    def __getitem__(self, key: int) -> bool:
        return key in self._pressed


class DummyAssets(AssetLoader):
    def __init__(self) -> None:
        super().__init__()
        self.loaded: list[tuple[str, tuple[int, int]]] = []

    def load_image(
        self,
        filename: str,
        size: tuple[int, int],
        *,
        rotate_left: bool = False,
    ) -> pygame.Surface:
        self.loaded.append((filename, size))
        return pygame.Surface(size)


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _spec(mass: float = 1.0, thrust: float = 1200.0, hull: float = 100.0) -> ShipSpec:
    return ShipSpec(
        name="Testschiff",
        sprite="CopperShip1.png",
        tint=None,
        mass=mass,
        thrust=thrust,
        hull=hull,
        weapon_slots=1,
        accessory_slots=1,
    )


def _player(y: int, spec: ShipSpec | None = None) -> Player:
    return Player((50, y), spec or _spec())


def _meteorite(
    rect: pygame.Rect,
    speed_x: float = 200.0,
    *,
    hp: int = 10,
    contact_damage: int = 15,
) -> Meteorite:
    return Meteorite(rect, speed_x, hp=hp, contact_damage=contact_damage)


def _bonus_weapon(max_ammo: int = 3) -> WeaponSpec:
    return WeaponSpec(
        WeaponKind.STANDARD,
        "Bonus",
        max_ammo,
        permanent=False,
        damage=20,
        fire_cooldown=0.15,
    )


def test_main_menu_navigation_wraps(context: GameContext) -> None:
    menu = MainMenu(context)
    assert menu.selected_index == 0

    menu.handle_event(_keydown(pygame.K_UP))
    assert menu.selected_index == len(MENU_ITEMS) - 1

    menu.handle_event(_keydown(pygame.K_DOWN))
    assert menu.selected_index == 0


def test_main_menu_remembers_cursor(context: GameContext) -> None:
    menu = MainMenu(context)
    menu.handle_event(_keydown(pygame.K_DOWN))
    menu.handle_event(_keydown(pygame.K_DOWN))
    assert context.state.menu_index == 2

    # Rückkehr aus einer anderen Szene: der Cursor steht wieder auf demselben Punkt.
    assert MainMenu(context).selected_index == 2

    # Ein Speicherstand mit unmöglichem Index darf das Menü nicht zerlegen.
    context.state.menu_index = len(MENU_ITEMS) + 5
    assert MainMenu(context).selected_index == len(MENU_ITEMS) - 1


def test_main_menu_actions_map_to_transitions(context: GameContext) -> None:
    menu = MainMenu(context)
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.START_GAME


def test_ship_selection_navigation_wraps(context: GameContext) -> None:
    selection = ShipSelection(context)
    assert selection.cursor == 0

    selection.handle_event(_keydown(pygame.K_LEFT))
    assert selection.cursor == len(SHIPS) - 1
    # Der Cursor darf über gesperrte Schiffe laufen, die Auswahl bleibt unberührt.
    assert context.state.selected_ship_index == 0

    selection.handle_event(_keydown(pygame.K_RIGHT))
    assert selection.cursor == 0


def test_ship_selection_escape_returns_without_change(context: GameContext) -> None:
    selection = ShipSelection(context)
    selection.handle_event(_keydown(pygame.K_RIGHT))
    selection.handle_event(_keydown(pygame.K_ESCAPE))
    assert selection._transition is Transition.MAIN_MENU
    assert context.state.selected_ship_index == 0


def test_music_player_track_cycle(monkeypatch: pytest.MonkeyPatch) -> None:
    player = MusicPlayer()
    monkeypatch.setattr(player, "_load_and_play", lambda filename: None)

    indices = []
    for _ in range(len(GAME_MUSIC_TRACKS) + 1):
        player.advance_track()
        indices.append(player.track_index)

    expected = [(i + 1) % len(GAME_MUSIC_TRACKS) for i in range(len(GAME_MUSIC_TRACKS) + 1)]
    assert indices == expected


def test_game_state_selected_ship() -> None:
    state = GameState(selected_ship_index=1)
    assert state.selected_ship is SHIPS[1]


def test_all_ship_variants_are_available() -> None:
    expected = {
        f"{color}Ship{variant}.png"
        for color in ("Copper", "Emerald", "Gold")
        for variant in range(1, 8)
    }
    assert set(SHIP_IMAGES) == expected
    assert len(SHIP_IMAGES) == 21


def test_ship_images_use_ship_subfolder() -> None:
    assert ship_image_path("CopperShip1.png").parts[-3:] == (
        "images",
        "ships",
        "CopperShip1.png",
    )


def test_distance_score_tracks_light_years() -> None:
    score = DistanceScore(light_years_per_second=12.0)
    score.update(2.5)
    assert score.light_years == 30.0
    assert score.formatted() == "000030"


def test_format_light_years() -> None:
    assert format_light_years(123.9) == "000123"


def test_distance_score_uses_rate_multiplier() -> None:
    score = DistanceScore(light_years_per_second=10.0)
    score.set_rate_multiplier(2.5)
    score.update(2.0)
    assert score.light_years == 50.0


def test_all_ship_sprites_exist() -> None:
    for spec in SHIPS:
        assert ship_image_path(spec.sprite).exists(), spec.sprite


def test_ship_spec_derived_values() -> None:
    spec = _spec(mass=2.0, thrust=800.0, hull=99.6)
    assert spec.acceleration == 400.0
    assert spec.max_speed == 800.0 / DRAG
    assert spec.agility == DRAG / 2.0
    assert spec.hp == 100


def test_ship_spec_rejects_invalid_values() -> None:
    with pytest.raises(ValueError):
        _spec(mass=0.0)
    with pytest.raises(ValueError):
        _spec(thrust=-1.0)
    with pytest.raises(ValueError):
        ShipSpec(
            name="Bad",
            sprite="CopperShip1.png",
            tint=None,
            mass=1.0,
            thrust=100.0,
            hull=100.0,
            weapon_slots=-1,
            accessory_slots=0,
        )


def test_player_accelerates_under_thrust() -> None:
    player = _player(300)

    player.update(0.1, InputFrame.UP)
    assert player.velocity < 0
    assert player.rect.y < 300


def test_player_drifts_after_release() -> None:
    player = _player(300)
    player.update(0.1, InputFrame.UP)
    y_after_thrust = player.rect.y

    player.update(0.1, InputFrame.NONE)
    assert player.velocity < 0  # Trägheit: ohne Schub noch in Bewegung
    assert player.rect.y < y_after_thrust


def test_heavier_ship_accelerates_slower() -> None:
    light = _player(300, _spec(mass=0.5))
    heavy = _player(300, _spec(mass=2.5))

    light.update(0.1, InputFrame.DOWN)
    heavy.update(0.1, InputFrame.DOWN)
    assert light.velocity > heavy.velocity > 0


def test_player_stops_at_top() -> None:
    player = _player(5)

    player.update(0.5, InputFrame.UP)
    assert player.rect.y == 0
    assert player.velocity == 0


def test_player_stops_at_bottom() -> None:
    player = _player(600 - 64 - 5)

    player.update(0.5, InputFrame.DOWN)
    assert player.rect.y == 600 - 64
    assert player.velocity == 0


def test_set_vertical_position_syncs_float_and_rect() -> None:
    player = _player(300)
    player.set_vertical_position(123.7)
    assert player._y == 123.7
    assert player.rect.y == 124


def test_meteorite_moves_left_without_vertical_change() -> None:
    met = _meteorite(pygame.Rect(800, 100, 44, 44))
    met.update(0.1, player_y=300)
    assert met.rect.x == 800 - round(200.0 * 0.1)
    assert met.rect.y == 100


def test_meteorite_is_off_screen() -> None:
    assert _meteorite(pygame.Rect(-50, 100, 44, 44)).is_off_screen is True
    assert _meteorite(pygame.Rect(0, 100, 44, 44)).is_off_screen is False


def test_spawn_meteorite_uses_configured_sizes_and_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for variant in METEORITE_VARIANTS:
        monkeypatch.setattr("meteorite_dash.entities.METEORITE_VARIANTS", (variant,))
        meteorite = spawn_meteorite(random.Random(0), (800, 600))
        expected_size = variant.radius * 2

        assert meteorite.rect.size == (expected_size, expected_size)
        assert meteorite.image_name in variant.images
        assert meteorite.hp == variant.hp
        assert meteorite.contact_damage == variant.contact_damage

        # Das Bild wird erst beim Zeichnen geholt — in Fenstergröße, hier 1:1.
        assets = DummyAssets()
        meteorite.draw(RenderContext(pygame.Surface((800, 600)), Viewport(800, 600), assets))
        assert assets.loaded == [(meteorite.image_name, (expected_size, expected_size))]


def test_meteorite_draw_scales_image_to_viewport(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("meteorite_dash.entities.METEORITE_VARIANTS", (METEORITE_VARIANTS[0],))
    meteorite = spawn_meteorite(random.Random(0), (800, 600))
    assets = DummyAssets()
    meteorite.draw(RenderContext(pygame.Surface((1600, 1200)), Viewport(1600, 1200), assets))

    expected_size = METEORITE_VARIANTS[0].radius * 4
    assert assets.loaded[0][1] == (expected_size, expected_size)
    # Die Hitbox bleibt im Referenzraum.
    assert meteorite.rect.size == (expected_size // 2, expected_size // 2)


def test_meteorite_draw_without_assets_falls_back_to_circle() -> None:
    surface = pygame.Surface((800, 600))
    meteorite = Meteorite(
        pygame.Rect(100, 100, 40, 40), 0.0, "AsteroidTiny.png", hp=10, contact_damage=1
    )
    meteorite.draw(RenderContext(surface, Viewport(800, 600)))
    assert surface.get_at((120, 120))[:3] == METEORITE_COLOR


def test_wave_enemy_moves_left_and_oscillates() -> None:
    enemy = WaveEnemy(pygame.Rect(800, 200, 44, 44), speed_x=180.0)
    enemy.update(0.05, player_y=0)
    assert enemy.rect.x < 800
    assert enemy.rect.y > 200  # erste Halbwelle: sin>0 -> y waechst nach unten


def test_hunter_enemy_moves_toward_player() -> None:
    enemy = HunterEnemy(pygame.Rect(800, 0, 44, 44), speed_x=160.0)
    enemy.update(0.1, player_y=400)
    assert enemy.rect.x < 800
    assert enemy.rect.y > 0  # bewegt sich nach unten Richtung Spieler


def test_hunter_enemy_does_not_overshoot() -> None:
    enemy = HunterEnemy(pygame.Rect(800, 300, 44, 44), speed_x=160.0)  # center y = 322
    enemy.update(1.0, player_y=330)  # nahes Ziel, grosser dt
    assert enemy.rect.centery == 330


def test_collides_with_any() -> None:
    player = solid(pygame.Rect(50, 100, 64, 64))
    hit = _meteorite(pygame.Rect(80, 120, 44, 44))
    miss = _meteorite(pygame.Rect(700, 500, 44, 44))
    assert collides_with_any(player, [miss, hit]) is True
    assert collides_with_any(player, [miss]) is False
    assert collides_with_any(player, []) is False


def _fake_factory(rng: random.Random, screen_size: tuple[int, int]) -> Meteorite:
    return _meteorite(pygame.Rect(screen_size[0], 0, 10, 10), speed_x=100.0)


def test_spawner_no_spawn_before_interval() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    assert spawner.update(0.5) == []


def test_spawner_spawns_after_interval() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    spawner.update(0.5)
    spawned = spawner.update(0.6)
    assert len(spawned) == 1
    assert isinstance(spawned[0], Meteorite)


def test_spawner_multiple_spawns_in_one_update() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    assert len(spawner.update(3.5)) == 3


def test_spawner_retries_rejected_candidates() -> None:
    spawner = Spawner([SpawnEntry(1.0, _fake_factory)], (800, 600), random.Random(0), (1.0, 1.0))
    seen: list[Meteorite] = []

    def accept(candidate: Meteorite) -> bool:
        seen.append(candidate)
        return len(seen) == 2

    spawned = spawner.update(1.0, accept=accept)
    assert len(seen) == 2
    assert spawned == [seen[1]]


def test_spawner_skips_spawn_after_max_attempts() -> None:
    spawner = Spawner(
        [SpawnEntry(1.0, _fake_factory)],
        (800, 600),
        random.Random(0),
        (1.0, 1.0),
        max_attempts=3,
    )
    attempts = 0

    def reject(candidate: Meteorite) -> bool:
        nonlocal attempts
        attempts += 1
        return False

    assert spawner.update(1.0, accept=reject) == []
    assert attempts == 3
    # Timer läuft normal weiter: der nächste Wurf ist wieder frei.
    assert len(spawner.update(1.0)) == 1


def test_game_scene_collision_opens_death_screen(context: GameContext) -> None:
    scene = GameScene(context)
    scene.sim.score.light_years = 42.0
    scene.sim.entities.append(
        _meteorite(scene.sim.player.rect.copy(), speed_x=0.0, contact_damage=999)
    )
    scene.step(InputFrame.NONE)
    scene.update(DEATH_DELAY_SECONDS)  # Explosion läuft, dann erst der Wechsel
    assert scene._transition is Transition.DEATH_SCREEN
    assert context.state.final_light_years > 42.0


def test_game_scene_collision_reduces_hp_before_death(context: GameContext) -> None:
    scene = GameScene(context)
    scene.sim.entities.append(
        _meteorite(scene.sim.player.rect.copy(), speed_x=0.0, contact_damage=30)
    )
    scene.step(InputFrame.NONE)
    assert scene._transition is None
    assert scene.sim.player.hp == scene.sim.player.max_hp - 30


def test_game_scene_removes_off_screen_entities(context: GameContext) -> None:
    scene = GameScene(context)
    scene.sim.entities.append(_meteorite(pygame.Rect(-100, 300, 44, 44), speed_x=0.0))
    scene.step(InputFrame.NONE)
    assert scene.sim.entities == []


def test_game_scene_updates_score(context: GameContext) -> None:
    scene = GameScene(context)
    scene.update(0.5)
    assert scene.sim.score.light_years > 0


def test_from_pressed_maps_held_keys() -> None:
    assert from_pressed(FakeKeys({pygame.K_UP, pygame.K_SPACE})) == InputFrame.UP | InputFrame.FIRE
    assert from_pressed(FakeKeys({pygame.K_DOWN})) == InputFrame.DOWN
    assert from_pressed(FakeKeys(set())) == InputFrame.NONE


def test_weapon_loadout_starts_with_full_standard_ammo() -> None:
    loadout = WeaponLoadout(2)
    assert loadout.active.spec is STANDARD_WEAPON
    assert loadout.active.ammo == STANDARD_WEAPON.max_ammo


def test_weapon_loadout_fire_consumes_ammo() -> None:
    loadout = WeaponLoadout(1)
    assert loadout.fire() is True
    assert loadout.active.ammo == STANDARD_WEAPON.max_ammo - 1
    assert loadout.can_fire() is True


def test_weapon_loadout_cannot_fire_when_empty() -> None:
    loadout = WeaponLoadout(1)
    for _ in range(STANDARD_WEAPON.max_ammo):
        loadout.fire()
    assert loadout.can_fire() is False
    assert loadout.fire() is False


def test_weapon_loadout_refill_standard() -> None:
    loadout = WeaponLoadout(1)
    loadout.fire()
    loadout.fire()
    loadout.refill_standard()
    assert loadout.active.ammo == STANDARD_WEAPON.max_ammo


def test_weapon_loadout_cycle_requires_multiple_weapons() -> None:
    loadout = WeaponLoadout(1)
    loadout.cycle_weapon()
    assert loadout.active_index == 0


def test_weapon_loadout_adds_and_cycles_bonus_weapon() -> None:
    loadout = WeaponLoadout(2)
    bonus = _bonus_weapon()
    assert loadout.add_weapon(bonus) is True
    loadout.cycle_weapon()
    assert loadout.active.spec.name == "Bonus"
    loadout.cycle_weapon()
    assert loadout.active.spec.permanent is True


def test_weapon_loadout_removes_empty_bonus_weapon() -> None:
    loadout = WeaponLoadout(2)
    bonus = _bonus_weapon(max_ammo=1)
    loadout.add_weapon(bonus)
    loadout.active_index = 1
    loadout.fire()
    assert len(loadout.weapons) == 1
    assert loadout.active.spec.permanent is True


def test_weapon_loadout_respects_slot_limit() -> None:
    loadout = WeaponLoadout(2)
    bonus = _bonus_weapon()
    assert loadout.add_weapon(bonus) is True
    assert loadout.add_weapon(bonus) is False


def test_projectile_moves_right() -> None:
    projectile = Projectile(pygame.Rect(10, 10, 8, 4), speed_x=100.0, damage=10)
    projectile.update(0.1)
    assert projectile.rect.x == 10 + round(100.0 * 0.1)


def test_spawn_projectile_starts_at_player_front() -> None:
    player = _player(300)
    projectile = spawn_projectile(player, damage=STANDARD_WEAPON_DAMAGE)
    assert projectile.rect.left == player.rect.right
    assert projectile.rect.centery == player.rect.centery


def test_ammo_pickup_does_not_damage_player() -> None:
    pickup = AmmoPickup(pygame.Rect(60, 120, 24, 24), speed_x=100.0)
    assert pickup.damages_player is False


def test_collides_with_any_ignores_ammo_pickups() -> None:
    player = solid(pygame.Rect(50, 100, 64, 64))
    pickup = AmmoPickup(pygame.Rect(60, 120, 24, 24), speed_x=100.0)
    assert collides_with_any(player, [pickup]) is False


def test_collect_pickups() -> None:
    player = solid(pygame.Rect(50, 100, 64, 64))
    pickup = AmmoPickup(pygame.Rect(60, 120, 24, 24), speed_x=100.0)
    meteorite = _meteorite(pygame.Rect(700, 500, 44, 44))
    entities: list[Entity] = [pickup, meteorite]
    collected = collect_pickups(player, entities)
    assert collected == [pickup]
    assert entities == [meteorite]


def test_spawn_ammo_pickup_uses_reference_size() -> None:
    pickup = spawn_ammo_pickup(random.Random(0), (800, 600))
    assert pickup.rect.size == AMMO_PICKUP_SIZE
    assert pickup.rect.left == 800


def test_game_scene_fires_projectile(context: GameContext) -> None:
    scene = GameScene(context)
    scene.step(InputFrame.FIRE)
    assert len(scene.sim.projectiles) == 1
    assert scene.sim.loadout.active.ammo == STANDARD_WEAPON.max_ammo - 1


def test_game_scene_ammo_pickup_refills_standard(context: GameContext) -> None:
    scene = GameScene(context)
    scene.sim.loadout.fire()
    scene.sim.loadout.fire()
    scene.sim.entities.append(AmmoPickup(scene.sim.player.rect.copy(), speed_x=0.0))
    scene.step(InputFrame.NONE)
    assert scene.sim.loadout.active.ammo == STANDARD_WEAPON.max_ammo


def test_player_starts_with_ship_hp() -> None:
    player = _player(300, _spec(hull=60.0))
    assert player.hp == 60
    assert player.max_hp == 60


def test_meteorite_take_damage() -> None:
    meteorite = _meteorite(pygame.Rect(0, 0, 44, 44), hp=40)
    assert meteorite.take_damage(10) is False
    assert meteorite.hp == 30
    assert meteorite.take_damage(30) is True
    assert meteorite.hp == 0


def test_large_meteorite_needs_seven_standard_shots() -> None:
    large = METEORITE_VARIANTS[-1]
    meteorite = _meteorite(pygame.Rect(0, 0, 120, 120), hp=large.hp)
    for _shot in range(6):
        assert meteorite.take_damage(STANDARD_WEAPON_DAMAGE) is False
    assert meteorite.hp == large.hp - 6 * STANDARD_WEAPON_DAMAGE
    assert meteorite.take_damage(STANDARD_WEAPON_DAMAGE) is True


def test_resolve_projectile_hits() -> None:
    meteorite = _meteorite(pygame.Rect(100, 100, 44, 44), hp=20)
    projectile = Projectile(pygame.Rect(90, 110, 16, 8), speed_x=100.0, damage=10)
    projectiles = [projectile]
    entities: list[Entity] = [meteorite]
    resolve_projectile_hits(projectiles, entities)
    assert projectiles == []
    assert len(entities) == 1
    assert meteorite.hp == 10

    projectiles.append(Projectile(pygame.Rect(90, 110, 16, 8), speed_x=100.0, damage=10))
    resolve_projectile_hits(projectiles, entities)
    assert projectiles == []
    assert entities == []


def test_resolve_projectile_hits_destroy_enemy() -> None:
    enemy = WaveEnemy(pygame.Rect(100, 100, 44, 44), speed_x=100.0)
    # Auf Höhe der Dreieck-Spitze: weiter oben deckt die Maske nichts ab.
    projectile = Projectile(pygame.Rect(90, 118, 16, 8), speed_x=100.0, damage=20)
    projectiles = [projectile]
    entities: list[Entity] = [enemy]
    resolve_projectile_hits(projectiles, entities)
    assert projectiles == []
    assert entities == []


def test_apply_contact_damage() -> None:
    player = solid(pygame.Rect(50, 100, 64, 64))
    meteorite = _meteorite(player.rect.copy(), contact_damage=25)
    entities: list[Entity] = [meteorite]
    hp = apply_contact_damage(player, 100, entities)
    assert hp == 75
    assert entities == []


def test_standard_weapon_spec_values() -> None:
    assert STANDARD_WEAPON.damage == STANDARD_WEAPON_DAMAGE
    assert STANDARD_WEAPON.fire_cooldown == SHOOT_COOLDOWN
    assert STANDARD_WEAPON.sound == "standard-gun.mp3"


def test_game_scene_plays_weapon_sound_on_shot(
    context: GameContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    played: list[str] = []
    monkeypatch.setattr(
        context.music,
        "play_sound_effect",
        lambda filename: played.append(filename),
    )
    scene = GameScene(context)
    scene.step(InputFrame.FIRE)
    assert played == ["standard-gun.mp3"]


def test_game_scene_projectile_destroys_meteorite(context: GameContext) -> None:
    scene = GameScene(context)
    scene.sim.entities.append(_meteorite(pygame.Rect(110, 120, 44, 44), hp=10))
    scene.step(InputFrame.FIRE)
    assert scene.sim.entities == []
    assert scene.sim.projectiles == []
