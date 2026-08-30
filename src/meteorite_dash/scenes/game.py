import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COIN_BONUS_NOTICE_SECONDS,
    COIN_BONUS_TOP_RIGHT,
    COIN_COLOR,
    COINS_TOP_RIGHT,
    HP_HUD_TOP_LEFT,
    MAX_STEPS_PER_FRAME,
    REPLAY_BEST_NAME,
    REPLAY_LAST_NAME,
    SCORE_ALPHA,
    SCORE_FONT_SIZE,
    SCORE_TOP_RIGHT,
    SHIELD_HUD_COLOR,
    SHIELD_HUD_TOP_LEFT,
    SIM_DT,
    TEXT_COLOR,
    WEAPON_HUD_FONT_SIZE,
    WEAPON_HUD_TOP_LEFT,
)
from meteorite_dash.context import GameContext
from meteorite_dash.inputs import InputFrame, from_pressed
from meteorite_dash.render import RenderContext
from meteorite_dash.replay import Recorder, Replay
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import format_coins
from meteorite_dash.simulation import EventKind, RunConfig, SimEvent, Simulation, pick_seed

# Float-Akkumulator: knapp unter SIM_DT zählt noch als voller Tick, sonst frisst
# Rundung bei exakten Vielfachen einen Schritt.
_STEP_EPSILON = 1e-9


class GameScene(Scene):
    """Spiel-Loop um die deterministische `Simulation`.

    Die Szene macht nur drei Dinge: Wandzeit in feste Ticks umrechnen, Tastatur
    in `InputFrame`s übersetzen und den Zustand über den `RenderContext`
    zeichnen. Spielregeln leben in `simulation.py`.
    """

    def __init__(self, context: GameContext, *, seed: int | None = None) -> None:
        super().__init__(context)
        self.seed = seed if seed is not None else pick_seed()
        self.sim = Simulation(self.run_config(self.seed))
        self.recorder = Recorder(self.sim.config)
        self._accumulator = 0.0
        # Flanken (Waffenwechsel) aus Events, bis zum nächsten Tick gesammelt.
        self._pending = InputFrame.NONE
        self._bonus_notice = ""
        self._bonus_notice_ttl = 0.0

    def run_config(self, seed: int) -> RunConfig:
        state = self.context.state
        spec = state.selected_ship
        equipped = tuple(acc.id for acc in state.progress.equipped_accessories(spec))
        return RunConfig(seed, spec.name, equipped)

    def ship_image(self, size: tuple[int, int]) -> pygame.Surface:
        """Schiffssprite in Fenstergröße (gecacht), mit der gewählten Färbung."""
        spec = self.context.state.selected_ship
        tint = self.context.state.progress.ship_tint(spec)
        return self.context.assets.load_ship(spec.sprite, size, tint)

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()
        # Guthaben auch bei Abbruch (Escape) gutschreiben und sichern.
        self.context.state.progress.add_coins(self.sim.coins_collected)
        self.context.save_progress()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == GAME_MUSIC_ENDED:
            self.context.music.advance_track()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.finish(Transition.MAIN_MENU)
            elif event.key == pygame.K_r:
                self._pending |= InputFrame.SWAP_WEAPON

    def update(self, dt: float) -> None:
        # Deko läuft mit Wandzeit; nur die Simulation tickt fest.
        self.context.starfield.update(dt)
        self._bonus_notice_ttl = max(0.0, self._bonus_notice_ttl - dt)

        held = from_pressed(pygame.key.get_pressed())
        self._accumulator += dt
        steps = 0
        while self._accumulator >= SIM_DT - _STEP_EPSILON and steps < MAX_STEPS_PER_FRAME:
            self._accumulator -= SIM_DT
            steps += 1
            self.step(held | self._pending)
            self._pending = InputFrame.NONE
            if self.sim.is_over:
                break
        if steps >= MAX_STEPS_PER_FRAME:
            # Hänger: Rest verfällt, statt in einer Todesspirale aufzuholen.
            self._accumulator = 0.0

    def step(self, inputs: InputFrame) -> list[SimEvent]:
        """Genau ein Simulations-Tick plus Reaktion der Szene auf die Events."""
        if not self.sim.is_over:
            self.recorder.record(inputs)
        events = self.sim.step(inputs)
        for event in events:
            self._on_event(event)
        return events

    def _on_event(self, event: SimEvent) -> None:
        if event.kind is EventKind.FIRED and event.sound is not None:
            self.context.music.play_sound_effect(event.sound)
        elif event.kind is EventKind.COIN_BONUS:
            self._bonus_notice = f"BONUS +{event.value}"
            self._bonus_notice_ttl = COIN_BONUS_NOTICE_SECONDS
        elif event.kind is EventKind.DEATH:
            state = self.context.state
            state.final_light_years = self.sim.light_years
            state.final_coins = self.sim.coins_collected
            state.final_seed = self.seed
            state.last_replay = self._store_replay(self.recorder.finish(self.sim))
            self.finish(Transition.DEATH_SCREEN)

    def _store_replay(self, replay: Replay) -> Replay:
        """`last` immer, `best` nur bei neuer Bestweite. Ohne Store bleibt es im Speicher."""
        store = self.context.replays
        if store is None:
            return replay
        store.save(REPLAY_LAST_NAME, replay)
        best = store.load(REPLAY_BEST_NAME)
        if best is None or replay.light_years > best.light_years:
            store.save(REPLAY_BEST_NAME, replay)
        return replay

    def draw(self) -> None:
        screen = self.context.screen
        ctx = RenderContext(screen, self.context.viewport, self.context.assets)
        screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(screen)
        for entity in self.sim.entities:
            entity.draw(ctx)
        # Münzen über den Gefahren: Collectibles bleiben sichtbar, auch wenn ein
        # langsamerer Gegner kurz überholt wird.
        for formation in self.sim.formations:
            formation.draw(ctx)
        for projectile in self.sim.projectiles:
            projectile.draw(ctx)
        self._draw_player(ctx)
        self._draw_weapon_hud()
        self._draw_hp_hud()
        self._draw_shield_hud()
        self._draw_score()
        pygame.display.flip()

    def _draw_player(self, ctx: RenderContext) -> None:
        target = ctx.rect(self.sim.player.rect)
        ctx.surface.blit(self.ship_image(target.size), target)

    def _draw_shield_hud(self) -> None:
        if self.sim.shield_charges <= 0:
            return
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        text = font.render(f"SCHILD x{self.sim.shield_charges}", True, SHIELD_HUD_COLOR)
        text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(text, text.get_rect(topleft=vp.point(*SHIELD_HUD_TOP_LEFT)))

    def _draw_hp_hud(self) -> None:
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        player = self.sim.player
        hp_text = font.render(f"HP {player.hp}/{player.max_hp}", True, TEXT_COLOR)
        hp_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(hp_text, hp_text.get_rect(topleft=vp.point(*HP_HUD_TOP_LEFT)))

    def _draw_weapon_hud(self) -> None:
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        active = self.sim.loadout.active
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

        score_text = font.render(f"LIGHTYRS {self.sim.score.formatted()}", True, TEXT_COLOR)
        score_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(
            score_text, score_text.get_rect(topright=vp.point(*SCORE_TOP_RIGHT))
        )

        coins_text = font.render(
            f"COINS {format_coins(self.sim.coins_collected)}", True, COIN_COLOR
        )
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
