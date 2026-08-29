import functools
import random

import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.coins import CoinFormation, coin_rects, is_clear, spawn_coin_formation
from meteorite_dash.combat import apply_contact_damage, resolve_projectile_hits
from meteorite_dash.config import (
    AMMO_PICKUP_WEIGHT,
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
    METEORITE_WEIGHT,
    PLAYER_SIZE,
    PLAYER_START_POSITION,
    SCORE_ALPHA,
    SCORE_FONT_SIZE,
    SCORE_LIGHT_YEARS_PER_SECOND,
    SCORE_TOP_RIGHT,
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
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import DistanceScore, format_coins
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.weapons import WeaponLoadout


class GameScene(Scene):
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
        self._bonus_notice = ""
        self._bonus_notice_ttl = 0.0
        self._build()

    def _scales(self) -> tuple[float, float, float]:
        vp = self.context.viewport
        return vp.scale_x, vp.scale_y, vp.scale

    def _scaled_player_size(self, su: float) -> tuple[int, int]:
        return (round(PLAYER_SIZE[0] * su), round(PLAYER_SIZE[1] * su))

    def _spawn_table(self, sx: float, sy: float, su: float) -> list[SpawnEntry[Entity]]:
        return [
            SpawnEntry(
                METEORITE_WEIGHT,
                functools.partial(spawn_meteorite, sx=sx, su=su, assets=self.context.assets),
            ),
            SpawnEntry(
                WAVE_ENEMY_WEIGHT,
                functools.partial(spawn_wave_enemy, sx=sx, sy=sy, su=su),
            ),
            SpawnEntry(
                HUNTER_ENEMY_WEIGHT,
                functools.partial(spawn_hunter_enemy, sx=sx, sy=sy, su=su),
            ),
            SpawnEntry(
                AMMO_PICKUP_WEIGHT,
                functools.partial(spawn_ammo_pickup, sx=sx, su=su),
            ),
        ]

    def _coin_table(self, sx: float, sy: float, su: float) -> list[SpawnEntry[CoinFormation]]:
        return [
            SpawnEntry(
                pattern.weight,
                functools.partial(spawn_coin_formation, pattern=pattern, sx=sx, sy=sy, su=su),
            )
            for pattern in COIN_PATTERNS
        ]

    def _build(self) -> None:
        sx, sy, su = self._scales()
        size = self.context.screen.get_size()
        spec = self.context.state.selected_ship
        image = self.context.assets.load_ship(spec.sprite, self._scaled_player_size(su), spec.tint)
        start = (round(PLAYER_START_POSITION[0] * sx), round(PLAYER_START_POSITION[1] * sy))
        self.player = Player(image, start, spec)
        self.loadout = WeaponLoadout(spec.weapon_slots)
        self.projectiles = []
        self._shoot_cooldown = 0.0
        rng = random.Random()
        self.spawner = Spawner(self._spawn_table(sx, sy, su), size, rng, SPAWN_INTERVAL_RANGE)
        self.coin_spawner = Spawner(
            self._coin_table(sx, sy, su), size, rng, COIN_SPAWN_INTERVAL_RANGE
        )

    def on_resize(self, size: tuple[int, int]) -> None:
        sx, sy, su = self._scales()
        spec = self.context.state.selected_ship
        image = self.context.assets.load_ship(spec.sprite, self._scaled_player_size(su), spec.tint)
        centery = self.player.rect.centery
        self.player.image = image
        self.player.rect = image.get_rect()
        self.player.rect.x = round(PLAYER_START_POSITION[0] * sx)
        self.player.rect.centery = centery
        # Re-clamp into the (possibly smaller) window; Player.update only blocks
        # further out-of-bounds movement, it never pulls a stranded ship back in.
        self.player.set_vertical_position(
            max(0, min(self.player.rect.y, size[1] - self.player.rect.height))
        )
        self.spawner.screen_size = size
        self.spawner.set_table(self._spawn_table(sx, sy, su))
        self.coin_spawner.screen_size = size
        self.coin_spawner.set_table(self._coin_table(sx, sy, su))

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()
        # Session-Summe auch bei Abbruch (Escape) gutschreiben.
        self.context.state.total_coins += self.coins_collected

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
        self.player.update(dt, keys, self.context.screen.get_height())
        self.context.starfield.update(dt)
        self.score.update(dt)
        self._update_shooting(dt, keys)

        self.entities.extend(self.spawner.update(dt, accept=self._accept_entity))
        player_y = self.player.rect.centery
        for entity in self.entities:
            entity.update(dt, player_y)
        self.entities = [entity for entity in self.entities if not entity.is_off_screen]

        screen_width = self.context.screen.get_width()
        for projectile in self.projectiles:
            projectile.update(dt)
        self.projectiles = [
            projectile
            for projectile in self.projectiles
            if not projectile.is_off_screen(screen_width)
        ]

        if collect_pickups(self.player.rect, self.entities):
            self.loadout.refill_standard()

        self._update_coins(dt, player_y)

        resolve_projectile_hits(self.projectiles, self.entities)

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
        sx, _, su = self._scales()
        self.projectiles.append(
            spawn_projectile(self.player, damage=fired_spec.damage, sx=sx, su=su)
        )
        self._shoot_cooldown = fired_spec.fire_cooldown
        if fired_spec.sound is not None:
            self.context.music.play_sound_effect(fired_spec.sound)

    def _clearance(self) -> int:
        return round(COIN_HAZARD_CLEARANCE * self.context.viewport.scale)

    def _hazard_rects(self) -> list[pygame.Rect]:
        return [entity.rect for entity in self.entities if entity.damages_player]

    def _accept_entity(self, entity: Entity) -> bool:
        """Gefahren spawnen nicht in ein Münz-Muster: gleich schnell → sonst dauerhaft verdeckt."""
        if not entity.damages_player:
            return True
        return is_clear([entity.rect], coin_rects(self.formations), self._clearance())

    def _accept_formation(self, formation: CoinFormation) -> bool:
        return is_clear(coin_rects([formation]), self._hazard_rects(), self._clearance())

    def _update_coins(self, dt: float, player_y: int) -> None:
        self.formations.extend(self.coin_spawner.update(dt, accept=self._accept_formation))
        for formation in self.formations:
            formation.update(dt, player_y)
            pickup = formation.collect(self.player.rect)
            self.coins_collected += pickup.total
            if pickup.bonus:
                self._bonus_notice = f"BONUS +{pickup.bonus}"
                self._bonus_notice_ttl = COIN_BONUS_NOTICE_SECONDS
        self.formations = [f for f in self.formations if not f.is_finished]
        self._bonus_notice_ttl = max(0.0, self._bonus_notice_ttl - dt)

    def draw(self) -> None:
        self.context.screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(self.context.screen)
        for entity in self.entities:
            entity.draw(self.context.screen)
        # Münzen über den Gefahren: Collectibles bleiben sichtbar, auch wenn ein
        # langsamerer Gegner kurz überholt wird.
        for formation in self.formations:
            formation.draw(self.context.screen)
        for projectile in self.projectiles:
            projectile.draw(self.context.screen)
        self.player.draw(self.context.screen)
        self._draw_weapon_hud()
        self._draw_hp_hud()
        self._draw_score()
        pygame.display.flip()

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
