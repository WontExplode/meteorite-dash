import functools
import random

import pygame

from meteorite_dash.accessories import AccessoryKind
from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.coins import CoinFormation, coin_rects, is_clear, spawn_coin_formation
from meteorite_dash.combat import absorb_contact, apply_contact_damage, resolve_projectile_hits
from meteorite_dash.config import (
    AMMO_PICKUP_WEIGHT,
    AMMO_RESERVE_BONUS,
    ARMOR_HP_BONUS,
    BACKGROUND_COLOR,
    COIN_BONUS_NOTICE_SECONDS,
    COIN_BONUS_TOP_RIGHT,
    COIN_COLOR,
    COIN_HAZARD_CLEARANCE,
    COIN_PATTERNS,
    COIN_SPAWN_INTERVAL_RANGE,
    COINS_TOP_RIGHT,
    HP_HUD_TOP_LEFT,
    HUNTER_ENEMY_WEIGHT,
    MAGNET_PULL_SPEED,
    MAGNET_RADIUS,
    METEORITE_WEIGHT,
    PLAYER_START_POSITION,
    REFERENCE_SIZE,
    SCORE_ALPHA,
    SCORE_FONT_SIZE,
    SCORE_LIGHT_YEARS_PER_SECOND,
    SCORE_TOP_RIGHT,
    SHIELD_CHARGES,
    SHIELD_HUD_COLOR,
    SHIELD_HUD_TOP_LEFT,
    SPAWN_INTERVAL_RANGE,
    TEXT_COLOR,
    WAVE_ENEMY_WEIGHT,
    WEAPON_HUD_FONT_SIZE,
    WEAPON_HUD_TOP_LEFT,
)
from meteorite_dash.context import GameContext
from meteorite_dash.entities import (
    Entity,
    collect_pickups,
    spawn_ammo_pickup,
    spawn_hunter_enemy,
    spawn_meteorite,
    spawn_wave_enemy,
)
from meteorite_dash.player import KeyStates, Player
from meteorite_dash.projectiles import Projectile, spawn_projectile
from meteorite_dash.render import RenderContext
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import DistanceScore, format_coins
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.weapons import WeaponLoadout

# Spawn-Tabellen sind fensterunabhängig: alle Fabriken arbeiten im Referenzraum.
SPAWN_TABLE: tuple[SpawnEntry[Entity], ...] = (
    SpawnEntry(METEORITE_WEIGHT, spawn_meteorite),
    SpawnEntry(WAVE_ENEMY_WEIGHT, spawn_wave_enemy),
    SpawnEntry(HUNTER_ENEMY_WEIGHT, spawn_hunter_enemy),
    SpawnEntry(AMMO_PICKUP_WEIGHT, spawn_ammo_pickup),
)
COIN_TABLE: tuple[SpawnEntry[CoinFormation], ...] = tuple(
    SpawnEntry(pattern.weight, functools.partial(spawn_coin_formation, pattern=pattern))
    for pattern in COIN_PATTERNS
)


class GameScene(Scene):
    """Spiel-Loop. Die Spiellogik läuft im Referenzraum (`REFERENCE_SIZE`);
    Fenstergröße und Vollbild betreffen nur das Zeichnen über den `RenderContext`."""

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.entities: list[Entity] = []
        self.projectiles: list[Projectile] = []
        # Münzen leben getrennt von `entities`: Berührung sammelt ein, schadet nicht.
        self.formations: list[CoinFormation] = []
        self.coins_collected = 0
        self.score = DistanceScore(SCORE_LIGHT_YEARS_PER_SECOND)
        self.loadout: WeaponLoadout
        self._shoot_cooldown = 0.0
        # Zubehör-Effekte (Issue #14), gesetzt in `_build` aus dem Fortschritt.
        self.shield_charges = 0
        self.magnet_enabled = False
        self._bonus_notice = ""
        self._bonus_notice_ttl = 0.0
        self._build()

    def ship_image(self, size: tuple[int, int]) -> pygame.Surface:
        """Schiffssprite in Fenstergröße (gecacht), mit der gewählten Färbung."""
        spec = self.context.state.selected_ship
        tint = self.context.state.progress.ship_tint(spec)
        return self.context.assets.load_ship(spec.sprite, size, tint)

    def _build(self) -> None:
        spec = self.context.state.selected_ship
        equipped = {acc.kind for acc in self.context.state.progress.equipped_accessories(spec)}
        extra_hp = ARMOR_HP_BONUS if AccessoryKind.ARMOR in equipped else 0
        self.player = Player(PLAYER_START_POSITION, spec, extra_hp=extra_hp)
        ammo_bonus = AMMO_RESERVE_BONUS if AccessoryKind.AMMO_RESERVE in equipped else 0
        self.loadout = WeaponLoadout(spec.weapon_slots, standard_ammo_bonus=ammo_bonus)
        self.shield_charges = SHIELD_CHARGES if AccessoryKind.SHIELD in equipped else 0
        self.magnet_enabled = AccessoryKind.MAGNET in equipped
        self.projectiles = []
        self._shoot_cooldown = 0.0
        rng = random.Random()
        self.spawner = Spawner(SPAWN_TABLE, REFERENCE_SIZE, rng, SPAWN_INTERVAL_RANGE)
        self.coin_spawner = Spawner(COIN_TABLE, REFERENCE_SIZE, rng, COIN_SPAWN_INTERVAL_RANGE)

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()
        # Guthaben auch bei Abbruch (Escape) gutschreiben und sichern.
        self.context.state.progress.add_coins(self.coins_collected)
        self.context.save_progress()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == GAME_MUSIC_ENDED:
            self.context.music.advance_track()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.finish(Transition.MAIN_MENU)
            elif event.key == pygame.K_r:
                self.loadout.cycle_weapon()

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys)
        self.context.starfield.update(dt)
        self.score.update(dt)
        self._update_shooting(dt, keys)

        self.entities.extend(self.spawner.update(dt, accept=self._accept_entity))
        player_y = self.player.rect.centery
        for entity in self.entities:
            entity.update(dt, player_y)
        self.entities = [entity for entity in self.entities if not entity.is_off_screen]

        for projectile in self.projectiles:
            projectile.update(dt)
        self.projectiles = [p for p in self.projectiles if not p.is_off_screen]

        if collect_pickups(self.player.rect, self.entities):
            self.loadout.refill_standard()

        self._update_coins(dt, player_y)

        resolve_projectile_hits(self.projectiles, self.entities)

        if self.shield_charges > 0 and absorb_contact(self.player.rect, self.entities):
            self.shield_charges -= 1
        else:
            self.player.hp = apply_contact_damage(self.player.rect, self.player.hp, self.entities)
        if self.player.hp <= 0:
            self.context.state.final_light_years = self.score.light_years
            self.context.state.final_coins = self.coins_collected
            self.finish(Transition.DEATH_SCREEN)

    def _update_shooting(self, dt: float, keys: KeyStates) -> None:
        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if not keys[pygame.K_SPACE] or self._shoot_cooldown > 0.0:
            return
        fired_spec = self.loadout.active.spec
        if not self.loadout.fire():
            return
        self.projectiles.append(spawn_projectile(self.player, damage=fired_spec.damage))
        self._shoot_cooldown = fired_spec.fire_cooldown
        if fired_spec.sound is not None:
            self.context.music.play_sound_effect(fired_spec.sound)

    def _hazard_rects(self) -> list[pygame.Rect]:
        return [entity.rect for entity in self.entities if entity.damages_player]

    def _accept_entity(self, entity: Entity) -> bool:
        """Gefahren spawnen nicht in ein Münz-Muster: gleich schnell → sonst dauerhaft verdeckt."""
        if not entity.damages_player:
            return True
        return is_clear([entity.rect], coin_rects(self.formations), COIN_HAZARD_CLEARANCE)

    def _accept_formation(self, formation: CoinFormation) -> bool:
        return is_clear(coin_rects([formation]), self._hazard_rects(), COIN_HAZARD_CLEARANCE)

    def _update_coins(self, dt: float, player_y: int) -> None:
        self.formations.extend(self.coin_spawner.update(dt, accept=self._accept_formation))
        for formation in self.formations:
            formation.update(dt, player_y)
            if self.magnet_enabled:
                formation.attract(self.player.rect.center, MAGNET_RADIUS, MAGNET_PULL_SPEED * dt)
            pickup = formation.collect(self.player.rect)
            self.coins_collected += pickup.total
            if pickup.bonus:
                self._bonus_notice = f"BONUS +{pickup.bonus}"
                self._bonus_notice_ttl = COIN_BONUS_NOTICE_SECONDS
        self.formations = [f for f in self.formations if not f.is_finished]
        self._bonus_notice_ttl = max(0.0, self._bonus_notice_ttl - dt)

    def draw(self) -> None:
        screen = self.context.screen
        ctx = RenderContext(screen, self.context.viewport, self.context.assets)
        screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(screen)
        for entity in self.entities:
            entity.draw(ctx)
        # Münzen über den Gefahren: Collectibles bleiben sichtbar, auch wenn ein
        # langsamerer Gegner kurz überholt wird.
        for formation in self.formations:
            formation.draw(ctx)
        for projectile in self.projectiles:
            projectile.draw(ctx)
        self._draw_player(ctx)
        self._draw_weapon_hud()
        self._draw_hp_hud()
        self._draw_shield_hud()
        self._draw_score()
        pygame.display.flip()

    def _draw_player(self, ctx: RenderContext) -> None:
        target = ctx.rect(self.player.rect)
        ctx.surface.blit(self.ship_image(target.size), target)

    def _draw_shield_hud(self) -> None:
        if self.shield_charges <= 0:
            return
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        text = font.render(f"SCHILD x{self.shield_charges}", True, SHIELD_HUD_COLOR)
        text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(text, text.get_rect(topleft=vp.point(*SHIELD_HUD_TOP_LEFT)))

    def _draw_hp_hud(self) -> None:
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        hp_text = font.render(f"HP {self.player.hp}/{self.player.max_hp}", True, TEXT_COLOR)
        hp_text.set_alpha(SCORE_ALPHA)
        hp_rect = hp_text.get_rect(topleft=vp.point(*HP_HUD_TOP_LEFT))
        self.context.screen.blit(hp_text, hp_rect)

    def _draw_weapon_hud(self) -> None:
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        active = self.loadout.active
        weapon_text = font.render(
            f"{active.spec.name} {active.ammo}/{active.spec.max_ammo}",
            True,
            TEXT_COLOR,
        )
        weapon_text.set_alpha(SCORE_ALPHA)
        weapon_rect = weapon_text.get_rect(topleft=vp.point(*WEAPON_HUD_TOP_LEFT))
        self.context.screen.blit(weapon_text, weapon_rect)

    def _draw_score(self) -> None:
        vp = self.context.viewport
        font = vp.font(SCORE_FONT_SIZE)

        score_text = font.render(f"LIGHTYRS {self.score.formatted()}", True, TEXT_COLOR)
        score_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(
            score_text, score_text.get_rect(topright=vp.point(*SCORE_TOP_RIGHT))
        )

        coins_text = font.render(f"COINS {format_coins(self.coins_collected)}", True, COIN_COLOR)
        coins_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(
            coins_text, coins_text.get_rect(topright=vp.point(*COINS_TOP_RIGHT))
        )

        if self._bonus_notice_ttl > 0:
            bonus_text = font.render(self._bonus_notice, True, COIN_COLOR)
            bonus_text.set_alpha(round(255 * self._bonus_notice_ttl / COIN_BONUS_NOTICE_SECONDS))
            self.context.screen.blit(
                bonus_text, bonus_text.get_rect(topright=vp.point(*COIN_BONUS_TOP_RIGHT))
            )
