import functools
import random

import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.config import (
    AMMO_PICKUP_WEIGHT,
    BACKGROUND_COLOR,
    HUNTER_ENEMY_WEIGHT,
    METEORITE_WEIGHT,
    PLAYER_SIZE,
    PLAYER_START_POSITION,
    SCORE_ALPHA,
    SCORE_FONT_SIZE,
    SCORE_LIGHT_YEARS_PER_SECOND,
    SCORE_TOP_RIGHT,
    SHOOT_COOLDOWN,
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
    collides_with_any,
    spawn_ammo_pickup,
    spawn_hunter_enemy,
    spawn_meteorite,
    spawn_wave_enemy,
)
from meteorite_dash.player import KeyStates, Player
from meteorite_dash.projectiles import Projectile, spawn_projectile
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import DistanceScore
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.weapons import WeaponLoadout


class GameScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.entities: list[Entity] = []
        self.projectiles: list[Projectile] = []
        self.score = DistanceScore(SCORE_LIGHT_YEARS_PER_SECOND)
        self.loadout: WeaponLoadout
        self._shoot_cooldown = 0.0
        self._build()

    def _scales(self) -> tuple[float, float, float]:
        vp = self.context.viewport
        return vp.scale_x, vp.scale_y, vp.scale

    def _scaled_player_size(self, su: float) -> tuple[int, int]:
        return (round(PLAYER_SIZE[0] * su), round(PLAYER_SIZE[1] * su))

    def _spawn_table(self, sx: float, sy: float, su: float) -> list[SpawnEntry]:
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
        self.spawner = Spawner(
            self._spawn_table(sx, sy, su), size, random.Random(), SPAWN_INTERVAL_RANGE
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

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()

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

        self.entities.extend(self.spawner.update(dt))
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

        if collides_with_any(self.player.rect, self.entities):
            self.context.state.final_light_years = self.score.light_years
            self.finish(Transition.DEATH_SCREEN)

    def _update_shooting(self, dt: float, keys: KeyStates) -> None:
        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if not keys[pygame.K_SPACE] or self._shoot_cooldown > 0.0:
            return
        if not self.loadout.fire():
            return
        sx, _, su = self._scales()
        self.projectiles.append(spawn_projectile(self.player, sx=sx, su=su))
        self._shoot_cooldown = SHOOT_COOLDOWN

    def draw(self) -> None:
        self.context.screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(self.context.screen)
        for entity in self.entities:
            entity.draw(self.context.screen)
        for projectile in self.projectiles:
            projectile.draw(self.context.screen)
        self.player.draw(self.context.screen)
        self._draw_weapon_hud()
        self._draw_score()
        pygame.display.flip()

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
        score_rect = score_text.get_rect(topright=vp.point(*SCORE_TOP_RIGHT))
        self.context.screen.blit(score_text, score_rect)
