"""Treffer-Feedback: prozedurale Sounds, Partikel/Blitz/Erschütterung, Schuss-Sperre."""

from random import Random

import pygame
import pytest

from meteorite_dash.coins import Coin, CoinFormation
from meteorite_dash.config import (
    AMMO_PICKUP_SIZE,
    COIN_RADIUS,
    DEATH_DELAY_SECONDS,
    FEEDBACK_MAX_PARTICLES,
    HEALTH_BAR_FLASH_SECONDS,
    HUD_FLASH_COLOR,
    HUD_FLASH_SECONDS,
    SIM_DT,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.effects import Effects
from meteorite_dash.entities import AmmoPickup, Meteorite, WaveEnemy
from meteorite_dash.inputs import InputFrame
from meteorite_dash.render import RenderContext
from meteorite_dash.scenes.base import Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.sfx import RECIPES, Sfx, SoundBank
from meteorite_dash.simulation import EventKind, SimEvent
from meteorite_dash.viewport import Viewport


def _meteorite(rect: pygame.Rect, *, hp: int = 10, contact_damage: int = 5) -> Meteorite:
    return Meteorite(rect, 0.0, hp=hp, contact_damage=contact_damage)


# --- Prozedurale Sounds ---------------------------------------------------------


def test_every_effect_has_a_recipe() -> None:
    assert set(RECIPES) == set(Sfx)


@pytest.mark.parametrize("effect", list(Sfx))
def test_effects_render_to_audible_sounds(effect: Sfx) -> None:
    pygame.init()
    bank = SoundBank()
    sound = bank._sound(effect)
    assert sound is not None
    assert sound.get_length() > 0.0
    # Zweiter Zugriff kommt aus dem Cache, wird also nicht neu synthetisiert.
    assert bank._sound(effect) is sound


def test_sound_bank_is_silent_without_mixer() -> None:
    pygame.mixer.quit()
    bank = SoundBank()
    bank.play(Sfx.HIT)  # kein Fehler, nur nichts zu hören
    assert bank._sound(Sfx.HIT) is None
    pygame.mixer.init()


# --- Effekt-Schicht -------------------------------------------------------------


def test_particles_expire_and_are_capped() -> None:
    effects = Effects(Random(1))
    for _ in range(200):
        effects.explosion((400, 300))
    assert len(effects.particles) <= FEEDBACK_MAX_PARTICLES

    for _ in range(100):
        effects.update(0.05)
    assert effects.particles == []


def test_flash_and_shake_fade_out() -> None:
    effects = Effects(Random(2))
    effects.damage((400, 300))
    effects.update(0.016)
    assert effects.offset != (0.0, 0.0)
    assert effects._flash_ttl > 0.0

    for _ in range(100):
        effects.update(0.05)
    assert effects.offset == (0.0, 0.0)
    assert effects._flash_ttl == 0.0


def test_stronger_shake_wins_over_a_running_one() -> None:
    effects = Effects(Random(3))
    effects.shake(10.0, 0.5)
    effects.shake(1.0, 0.1)  # schwächer: der laufende Ruck bleibt
    assert effects._shake_strength == 10.0
    effects.shake(20.0, 0.5)
    assert effects._shake_strength == 20.0


def test_effects_draw_without_error(context: GameContext) -> None:
    effects = Effects(Random(4))
    effects.explosion((400, 300))
    effects.shield((100, 200))
    effects.update(0.016)
    ctx = RenderContext(context.screen, Viewport(800, 600), context.assets, effects.offset)
    effects.draw(ctx)
    effects.draw_overlay(context.screen)


# --- Lebensleisten über getroffenen Zielen --------------------------------------


def test_health_bar_stays_hidden_until_first_hit(context: GameContext) -> None:
    effects = Effects(Random(5))
    meteorite = _meteorite(pygame.Rect(200, 200, 40, 40), hp=40)
    ctx = RenderContext(context.screen, Viewport(800, 600), context.assets)
    effects.draw_health_bars(ctx, [meteorite])
    assert effects._health_bars == {}

    meteorite.take_damage(10)
    effects.draw_health_bars(ctx, [meteorite])
    fx = effects._health_bars[id(meteorite)]
    assert fx.hp == 30
    assert fx.flash_ttl == HEALTH_BAR_FLASH_SECONDS
    assert fx.shake_ttl > 0.0


def test_health_bar_punches_again_on_further_damage(context: GameContext) -> None:
    effects = Effects(Random(6))
    enemy = WaveEnemy(pygame.Rect(300, 120, 44, 44), 0.0)
    enemy.take_damage(10)
    ctx = RenderContext(context.screen, Viewport(800, 600), context.assets)
    effects.draw_health_bars(ctx, [enemy])
    for _ in range(20):
        effects.update(0.05)
    fx = effects._health_bars[id(enemy)]
    assert fx.flash_ttl == 0.0
    assert fx.shake_ttl == 0.0

    enemy.take_damage(5)
    effects.draw_health_bars(ctx, [enemy])
    fx = effects._health_bars[id(enemy)]
    assert fx.hp == enemy.hp
    assert fx.flash_ttl == HEALTH_BAR_FLASH_SECONDS
    assert fx.shake_ttl > 0.0


def test_health_bar_is_forgotten_when_the_target_is_gone(context: GameContext) -> None:
    effects = Effects(Random(7))
    meteorite = _meteorite(pygame.Rect(100, 80, 40, 40), hp=40)
    meteorite.take_damage(10)
    ctx = RenderContext(context.screen, Viewport(800, 600), context.assets)
    effects.draw_health_bars(ctx, [meteorite])
    assert id(meteorite) in effects._health_bars

    effects.draw_health_bars(ctx, [])
    assert effects._health_bars == {}

    pickup = AmmoPickup(pygame.Rect(0, 0, *AMMO_PICKUP_SIZE), 0.0)
    effects.draw_health_bars(ctx, [pickup])
    assert effects._health_bars == {}


def test_health_bar_draw_without_error(context: GameContext) -> None:
    effects = Effects(Random(8))
    meteorite = _meteorite(pygame.Rect(50, 10, 40, 40), hp=40)
    meteorite.take_damage(10)
    ctx = RenderContext(context.screen, Viewport(800, 600), context.assets, effects.offset)
    effects.draw_health_bars(ctx, [meteorite])
    effects.update(0.016)
    effects.draw_health_bars(ctx, [meteorite])


def test_scene_shows_health_bar_after_a_hit(context: GameContext) -> None:
    scene = GameScene(context, seed=11)
    player = scene.sim.player
    target = _meteorite(
        pygame.Rect(player.rect.right + 60, player.rect.centery - 20, 40, 40), hp=40
    )
    scene.sim.entities.append(target)
    scene.draw()
    assert id(target) not in scene.effects._health_bars

    events: list[SimEvent] = []
    for _ in range(30):
        events = scene.step(InputFrame.FIRE if not scene.sim.projectiles else InputFrame.NONE)
        if any(event.kind is EventKind.HIT for event in events):
            break
    assert any(event.kind is EventKind.HIT for event in events)
    assert target.hp < target.max_hp
    scene.draw()
    assert id(target) in scene.effects._health_bars


# --- Verdrahtung in der Spielszene ----------------------------------------------


def test_events_carry_the_place_they_happened(context: GameContext) -> None:
    scene = GameScene(context, seed=5)
    player = scene.sim.player

    target = _meteorite(pygame.Rect(player.rect.right + 60, player.rect.centery - 20, 40, 40))
    scene.sim.entities.append(target)
    events = scene.step(InputFrame.FIRE)
    fired = [event for event in events if event.kind is EventKind.FIRED]
    assert fired and fired[0].position[0] >= player.rect.right

    hits = []
    for _ in range(20):
        hits += [event for event in events if event.kind is EventKind.HIT]
        if hits:
            break
        events = scene.step(InputFrame.NONE)
    assert hits
    assert target.rect.collidepoint(hits[0].position)


def test_scene_spawns_feedback_for_every_event(context: GameContext) -> None:
    scene = GameScene(context, seed=6)
    player = scene.sim.player

    scene.sim.entities.append(AmmoPickup(player.rect.copy(), 0.0))
    scene.step(InputFrame.NONE)
    assert scene._hud_flash.get("weapon", 0.0) > 0.0

    diameter = COIN_RADIUS * 2
    coin = Coin(
        pygame.Rect(
            player.rect.centerx - COIN_RADIUS, player.rect.centery - COIN_RADIUS, diameter, diameter
        ),
        0.0,
    )
    scene.sim.formations.append(CoinFormation([coin], bonus=4))
    scene.step(InputFrame.NONE)
    assert scene._hud_flash.get("coins", 0.0) > 0.0
    assert scene.effects.particles


def test_hud_line_flashes_and_returns_to_its_colour(context: GameContext) -> None:
    scene = GameScene(context, seed=7)
    assert scene._hud_color("hp", TEXT_COLOR) == TEXT_COLOR
    scene._flash_hud("hp")
    assert scene._hud_color("hp", TEXT_COLOR) == HUD_FLASH_COLOR
    scene.update(HUD_FLASH_SECONDS)
    assert scene._hud_color("hp", TEXT_COLOR) == TEXT_COLOR


def test_death_waits_for_the_explosion(context: GameContext) -> None:
    scene = GameScene(context, seed=8)
    scene.sim.entities.append(_meteorite(scene.sim.player.rect.copy(), contact_damage=999))
    scene.step(InputFrame.NONE)
    # Endstand steht sofort, der Szenenwechsel wartet auf Explosion und Blitz.
    assert context.state.final_light_years > 0.0
    assert scene._transition is None
    assert scene.effects.particles

    scene.update(SIM_DT)
    assert scene._transition is None
    scene.update(DEATH_DELAY_SECONDS)
    assert scene._transition is Transition.DEATH_SCREEN


# --- Leertaste aus dem Menü ------------------------------------------------------


class _Keys:
    """Ersatz für `pygame.key.get_pressed()`: nur die Leertaste ist gedrückt."""

    def __init__(self, space: bool) -> None:
        self.space = space

    def __getitem__(self, key: int) -> bool:
        return self.space and key == pygame.K_SPACE


def test_held_space_from_the_menu_does_not_fire(
    context: GameContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = GameScene(context, seed=9)
    ammo_before = scene.sim.loadout.active.ammo

    # Die Leertaste bestätigt das Menü und ist beim ersten Frame noch unten.
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys(True))
    scene.update(SIM_DT)
    assert scene.sim.projectiles == []
    assert scene.sim.loadout.active.ammo == ammo_before

    # Loslassen bewaffnet den Schuss, der nächste Druck feuert.
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys(False))
    scene.update(SIM_DT)
    monkeypatch.setattr(pygame.key, "get_pressed", lambda: _Keys(True))
    scene.update(SIM_DT)
    assert len(scene.sim.projectiles) == 1
    assert scene.sim.loadout.active.ammo == ammo_before - 1


def test_ammo_pickup_size_is_unchanged() -> None:
    assert AmmoPickup(pygame.Rect(0, 0, *AMMO_PICKUP_SIZE), 0.0).rect.size == AMMO_PICKUP_SIZE
