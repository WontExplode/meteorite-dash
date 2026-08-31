"""Spiel-Szene: Fixstep-Loop um `Simulation`, Eingabe-Übersetzung, Ghost und HUD."""

import math
from collections.abc import Iterator

import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.config import (
    AMMO_PICKUP_COLOR,
    BACKGROUND_COLOR,
    COIN_BONUS_NOTICE_SECONDS,
    COIN_BONUS_TOP_RIGHT,
    COIN_COLOR,
    COINS_TOP_RIGHT,
    DAILY_REPLAY_PREFIX,
    DEATH_DELAY_SECONDS,
    DIFFICULTY_DEBUG_HUD_COLOR,
    DIFFICULTY_DEBUG_HUD_FONT_SIZE,
    DIFFICULTY_DEBUG_HUD_LINE_SPACING,
    DIFFICULTY_DEBUG_HUD_TOP_LEFT,
    GHOST_ALPHA,
    GHOST_FADE_SECONDS,
    GHOST_HUD_COLOR,
    GHOST_HUD_TOP_RIGHT,
    GHOST_LEAD_MAX_OFFSET,
    GHOST_LEAD_MIN_X,
    GHOST_LEAD_SOFT_LIGHT_YEARS,
    GHOST_TINT,
    HP_HUD_TOP_LEFT,
    HUD_FLASH_COLOR,
    HUD_FLASH_SECONDS,
    MAX_STEPS_PER_FRAME,
    REFERENCE_SIZE,
    REPLAY_BEST_NAME,
    REPLAY_LAST_NAME,
    SCORE_ALPHA,
    SCORE_FONT_SIZE,
    SCORE_TOP_RIGHT,
    SHIELD_HUD_COLOR,
    SHIELD_HUD_TOP_LEFT,
    SIM_DT,
    SIM_VERSION,
    TEXT_COLOR,
    WEAPON_HUD_FONT_SIZE,
    WEAPON_HUD_TOP_LEFT,
    Color,
)
from meteorite_dash.context import GameContext
from meteorite_dash.difficulty import DirectorKind
from meteorite_dash.effects import Effects
from meteorite_dash.ghost import Ghost
from meteorite_dash.identity import short_pubkey
from meteorite_dash.inputs import InputFrame, from_pressed
from meteorite_dash.mode_directors import (
    director_for_kind,
    director_kind_for_mode,
    director_version_for_kind,
)
from meteorite_dash.render import RenderContext
from meteorite_dash.replay import Recorder, Replay, RunMode
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import format_coins, format_light_years
from meteorite_dash.sfx import Sfx
from meteorite_dash.simulation import EventKind, RunConfig, SimEvent, Simulation, pick_seed

# Float-Akkumulator: knapp unter SIM_DT zählt noch als voller Tick, sonst frisst
# Rundung bei exakten Vielfachen einen Schritt.
_STEP_EPSILON = 1e-9


class GameScene(Scene):
    """Spiel-Loop um die deterministische `Simulation`.

    Die Szene macht nur drei Dinge: Wandzeit in feste Ticks umrechnen, Tastatur
    in `InputFrame`s übersetzen und den Zustand über den `RenderContext`
    zeichnen. Spielregeln leben in `simulation.py`.

    Aus jedem `SimEvent` entsteht zusätzlich Feedback: prozeduraler Sound
    (`sfx.py`) und Funken, Blitze und Erschütterung (`effects.py`). Beides ist
    reine Ausgabe und wirkt nie auf die Simulation zurück.

    Mit `spectate=` läuft sie als Zuschauer: Eingaben kommen aus dem Replay
    statt von der Tastatur, nichts wird aufgezeichnet, gutgeschrieben oder
    geteilt; am Ende zeigt der Death-Screen „REPLAY VON …“.

    Die Director-Art folgt dem Modus (`mode_directors`); `director_kind=`
    überschreibt sie für ein Rennen gegen einen fremden Lauf, Zuschauen nimmt
    immer die im Replay aufgezeichnete Art. So gelten für Spieler und Ghost
    dieselben Regeln.
    """

    def __init__(
        self,
        context: GameContext,
        *,
        seed: int | None = None,
        ghost: Replay | None = None,
        mode: RunMode = RunMode.FREE,
        label: str = "",
        spectate: Replay | None = None,
        director_kind: DirectorKind | None = None,
    ) -> None:
        super().__init__(context)
        self.spectate = spectate
        if spectate is not None:
            self.seed, self.mode, self.label = spectate.config.seed, spectate.mode, spectate.label
            config = spectate.config
            director_kind = spectate.director_kind
        else:
            self.seed = seed if seed is not None else pick_seed()
            self.mode = mode
            self.label = label
            config = self.run_config(self.seed)
            if director_kind is None:
                director_kind = director_kind_for_mode(self.mode)
        self.director_kind = director_kind
        self.sim = Simulation(config, director=director_for_kind(director_kind))
        self._spectate_inputs: Iterator[InputFrame] | None = (
            spectate.inputs() if spectate is not None else None
        )
        self.recorder = Recorder(
            self.sim.config,
            mode=self.mode,
            label=self.label,
            director_kind=director_kind,
            director_version=director_version_for_kind(director_kind),
        )
        # Ghost nur unter denselben Regeln (Seed, Modus, Director), beim Zuschauen nie.
        ghost_replay = None
        if spectate is None:
            candidate = ghost if ghost is not None else self.find_ghost(self.seed)
            if candidate is not None and self._is_compatible_ghost(candidate):
                ghost_replay = candidate
        self.ghost = Ghost(ghost_replay) if ghost_replay is not None else None
        self._ghost_images: dict[tuple[int, int], pygame.Surface] = {}
        # Deckkraft des Ghosts: voll, solange sein Lauf läuft; danach blendet er
        # aus, während ihn der eigene Vorsprung nach hinten schiebt.
        self._ghost_fade = 1.0
        self._accumulator = 0.0
        # Flanken (Waffenwechsel) aus Events, bis zum nächsten Tick gesammelt.
        self._pending = InputFrame.NONE
        self._bonus_notice = ""
        self._bonus_notice_ttl = 0.0
        self.effects = Effects()
        # HUD-Zeilen leuchten nach einem Ereignis kurz auf (Schlüssel -> Restzeit).
        self._hud_flash: dict[str, float] = {}
        # Der Tod bleibt kurz stehen, damit Explosion und Blitz sichtbar werden.
        self._death_delay = 0.0
        # Die Leertaste bestätigt auch das Menü: ein noch gehaltener Start-Druck
        # darf im Spiel nicht sofort einen Schuss auslösen. Erst loslassen zählt.
        self._fire_armed = False
        # Neuer Lauf: Stand des Teilens vom letzten Lauf gilt nicht mehr.
        if context.exchange is not None:
            context.exchange.publish_status = ""
            context.exchange.share_status = ""
        self._show_difficulty_debug = False

    def run_config(self, seed: int) -> RunConfig:
        """`RunConfig` aus Seed, gewähltem Schiff und dessen Zubehör für diesen Lauf.

        Zubehör ist Verbrauchsware: die in der `LoadoutScene` eingesetzten Teile
        werden hier aus dem Lager gebucht und gelten nur für diesen Lauf. Der
        Fortschritt wird sofort geschrieben — sonst wäre ein Absturz ein
        Gratis-Lauf.
        """
        state = self.context.state
        spec = state.selected_ship
        used = state.progress.consume_loadout(spec)
        self.context.save_progress()
        return RunConfig(seed, spec.name, tuple(acc.id for acc in used))

    def find_ghost(self, seed: int) -> Replay | None:
        """Weitesten Lauf zum Seed mit denselben Regeln (Modus, Director, Version) finden.

        Im Daily ist das der Tagesrekord, im Free nur bei erzwungenem Seed
        relevant (eigener Bestlauf oder Community-Läufe zu diesem Seed).
        """
        store = self.context.replays
        if store is None:
            return None
        return store.best_for_seed(
            seed,
            mode=self.mode,
            director_kind=self.director_kind,
            director_version=director_version_for_kind(self.director_kind),
        )

    def _is_compatible_ghost(self, replay: Replay) -> bool:
        return (
            replay.config.seed == self.seed
            and replay.mode is self.mode
            and replay.sim_version == SIM_VERSION
            and replay.director_kind is self.director_kind
            and replay.director_version == director_version_for_kind(self.director_kind)
        )

    def ghost_image(self, size: tuple[int, int]) -> pygame.Surface:
        """Halbtransparente Kopie des Ghost-Schiffs, pro Fenstergröße gecacht."""
        assert self.ghost is not None
        image = self._ghost_images.get(size)
        if image is None:
            sprite = self.ghost.replay.config.spec.sprite
            image = self.context.assets.load_ship(sprite, size, GHOST_TINT).copy()
            image.set_alpha(GHOST_ALPHA)
            self._ghost_images[size] = image
        return image

    def ship_image(self, size: tuple[int, int]) -> pygame.Surface:
        """Schiffssprite in Fenstergröße (gecacht), mit der gewählten Färbung —
        im Zuschauer-Modus das Schiff des Replays in seiner Standardfarbe."""
        spec = self.sim.config.spec
        if self.spectate is not None:
            tint = spec.tint
        else:
            tint = self.context.state.progress.ship_tint(spec)
        return self.context.assets.load_ship(spec.sprite, size, tint)

    def on_enter(self) -> None:
        """Startet die Spiel-Playlist."""
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        """Stoppt die Musik, schreibt gesammelte Münzen ins Guthaben und speichert."""
        self.context.music.stop()
        if self.spectate is not None:
            return  # fremder Lauf: keine Münzen fürs Zuschauen
        # Guthaben auch bei Abbruch (Escape) gutschreiben und sichern.
        self.context.state.progress.add_coins(self.sim.coins_collected)
        self.context.save_progress()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Track-Ende schaltet weiter; Escape bricht ab, `R` merkt den Waffenwechsel vor."""
        if event.type == GAME_MUSIC_ENDED:
            self.context.music.advance_track()
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.finish(Transition.MAIN_MENU)
            elif event.key == pygame.K_F3:
                self._show_difficulty_debug = not self._show_difficulty_debug
            elif event.key == pygame.K_r:
                self._pending |= InputFrame.SWAP_WEAPON

    def update(self, dt: float) -> None:
        """Wandzeit in feste Ticks umrechnen, `step` bis zu `MAX_STEPS_PER_FRAME`-mal.

        Sternenfeld, Effekte, Bonus-Hinweis und HUD-Aufleuchten laufen mit
        Wandzeit weiter (Deko). Bleibt Zeit übrig, weil das Limit griff,
        verfällt sie statt aufgeholt zu werden. Nach dem Tod tickt nur noch die
        Deko, bis `DEATH_DELAY_SECONDS` um sind.
        """
        # Deko läuft mit Wandzeit; nur die Simulation tickt fest.
        self.context.starfield.update(dt)
        self.effects.update(dt)
        if self.ghost is not None and self.ghost.finished:
            self._ghost_fade = max(0.0, self._ghost_fade - dt / GHOST_FADE_SECONDS)
        self._bonus_notice_ttl = max(0.0, self._bonus_notice_ttl - dt)
        self._hud_flash = {key: ttl - dt for key, ttl in self._hud_flash.items() if ttl - dt > 0.0}
        if self._death_delay > 0.0:
            self._death_delay -= dt
            if self._death_delay <= 0.0:
                self.finish(Transition.DEATH_SCREEN)
            return

        held = InputFrame.NONE if self.spectate else self._player_inputs()
        self._accumulator += dt
        steps = 0
        while self._accumulator >= SIM_DT - _STEP_EPSILON and steps < MAX_STEPS_PER_FRAME:
            self._accumulator -= SIM_DT
            steps += 1
            if self._spectate_inputs is not None:
                frame = next(self._spectate_inputs, None)
                if frame is None:
                    self._end_spectate()  # Aufzeichnung zu Ende, ohne Tod
                    break
                self.step(frame)
            else:
                self.step(held | self._pending)
                self._pending = InputFrame.NONE
            if self.sim.is_over or self._transition is not None:
                break
        if steps >= MAX_STEPS_PER_FRAME:
            # Hänger: Rest verfällt, statt in einer Todesspirale aufzuholen.
            self._accumulator = 0.0

    def _player_inputs(self) -> InputFrame:
        """Gehaltene Tasten; `FIRE` erst, nachdem die Leertaste einmal los war."""
        held = from_pressed(pygame.key.get_pressed())
        if self._fire_armed:
            return held
        if InputFrame.FIRE in held:
            return held & ~InputFrame.FIRE
        self._fire_armed = True
        return held

    def step(self, inputs: InputFrame) -> list[SimEvent]:
        """Genau ein Simulations-Tick plus Reaktion der Szene auf die Events."""
        if not self.sim.is_over and self.spectate is None:
            self.recorder.record(inputs)
        if self.ghost is not None:
            self.ghost.step()
        events = self.sim.step(inputs)
        for event in events:
            self._on_event(event)
        return events

    def _on_event(self, event: SimEvent) -> None:
        """Reagiert auf ein `SimEvent`: Feedback geben, bei `DEATH` den Lauf abschließen.

        Sound und Optik hängen an `event.position`; bei `DEATH` wandert der
        Endstand in den `GameState`, das Replay in den Store, und der Wechsel
        zum Death-Screen wartet `DEATH_DELAY_SECONDS` auf die Explosion.
        """
        self._feedback(event)
        if event.kind is EventKind.COIN_BONUS:
            self._bonus_notice = f"BONUS +{event.value}"
            self._bonus_notice_ttl = COIN_BONUS_NOTICE_SECONDS
        elif event.kind is EventKind.DEATH and self.spectate is not None:
            self._end_spectate()
        elif event.kind is EventKind.DEATH:
            state = self.context.state
            state.final_spectate_author = None
            state.final_light_years = self.sim.light_years
            state.final_coins = self.sim.coins_collected
            state.final_seed = self.seed
            state.final_mode = self.mode
            state.final_label = self.label
            state.final_record_light_years = (
                self.ghost.replay.light_years if self.ghost is not None else None
            )
            state.final_record_author = self.ghost.replay.author if self.ghost is not None else ""
            state.last_replay = self._store_replay(self.recorder.finish(self.sim))
            self._death_delay = DEATH_DELAY_SECONDS

    def _feedback(self, event: SimEvent) -> None:
        """Übersetzt ein `SimEvent` in Sound, Partikel, Blitz und HUD-Aufleuchten."""
        music = self.context.music
        kind = event.kind
        if kind is EventKind.FIRED:
            if event.sound is not None:
                music.play_sound_effect(event.sound)
            self.effects.hit(event.position)
            self._flash_hud("weapon")
        elif kind is EventKind.HIT:
            music.play_effect(Sfx.HIT)
            self.effects.hit(event.position)
        elif kind is EventKind.DESTROYED:
            music.play_effect(Sfx.EXPLOSION)
            self.effects.explosion(event.position)
        elif kind is EventKind.AMMO_PICKUP:
            music.play_effect(Sfx.AMMO)
            self.effects.pickup(event.position, AMMO_PICKUP_COLOR)
            self._flash_hud("weapon")
        elif kind is EventKind.COIN:
            music.play_effect(Sfx.COIN)
            self.effects.pickup(event.position, COIN_COLOR)
            self._flash_hud("coins")
        elif kind is EventKind.COIN_BONUS:
            music.play_effect(Sfx.BONUS)
            self.effects.pickup(event.position, COIN_COLOR)
            self._flash_hud("coins")
        elif kind is EventKind.SHIELD:
            music.play_effect(Sfx.SHIELD)
            self.effects.shield(event.position)
            self._flash_hud("shield")
        elif kind is EventKind.CONTACT:
            music.play_effect(Sfx.DAMAGE)
            self.effects.damage(event.position)
            self._flash_hud("hp")
        elif kind is EventKind.DEATH:
            music.play_effect(Sfx.DEATH)
            self.effects.death(event.position)

    def _flash_hud(self, key: str) -> None:
        """Lässt eine HUD-Zeile kurz aufleuchten."""
        self._hud_flash[key] = HUD_FLASH_SECONDS

    def _hud_color(self, key: str, base: Color) -> Color:
        """Blendet die Grundfarbe einer HUD-Zeile zur Aufleucht-Farbe und zurück."""
        ttl = self._hud_flash.get(key, 0.0)
        if ttl <= 0.0:
            return base
        factor = ttl / HUD_FLASH_SECONDS
        return (
            round(base[0] + (HUD_FLASH_COLOR[0] - base[0]) * factor),
            round(base[1] + (HUD_FLASH_COLOR[1] - base[1]) * factor),
            round(base[2] + (HUD_FLASH_COLOR[2] - base[2]) * factor),
        )

    def _end_spectate(self) -> None:
        """Zuschauer-Modus zu Ende: Zahlen des fremden Laufs zeigen, nichts speichern."""
        assert self.spectate is not None
        state = self.context.state
        state.final_light_years = self.sim.light_years
        state.final_coins = self.sim.coins_collected
        state.final_seed = self.seed
        state.final_mode = self.mode
        state.final_label = self.label
        state.final_record_light_years = None
        state.final_record_author = ""
        state.final_spectate_author = self.spectate.author
        state.last_replay = None  # fremder Lauf: nicht unter eigenem Namen teilbar
        self.finish(Transition.DEATH_SCREEN)

    def record_name(self) -> str:
        """Rekord-Datei: `best` im freien Lauf, `daily-<datum>` im Daily Run."""
        if self.mode is RunMode.DAILY:
            return f"{DAILY_REPLAY_PREFIX}{self.label}"
        return REPLAY_BEST_NAME

    def _store_replay(self, replay: Replay) -> Replay:
        """`last` immer, Rekord nur bei neuer Bestweite — die geht auch an die
        Community. Ohne Store bleibt es im Speicher."""
        store = self.context.replays
        if store is None:
            return replay
        store.save(REPLAY_LAST_NAME, replay)
        record = store.load(self.record_name())
        if record is None or replay.light_years > record.light_years:
            store.save(self.record_name(), replay)
            if self.context.exchange is not None:
                self.context.exchange.publish(replay)
        return replay

    def draw(self) -> None:
        """Zeichnet Sternenfeld, Welt (inkl. Lebensleisten und Effekte), Blitz und HUD.

        Die Erschütterung steckt im `offset` des `RenderContext`: die Welt
        wackelt, Sternenfeld und HUD bleiben ruhig und lesbar.
        """
        screen = self.context.screen
        ctx = RenderContext(screen, self.context.viewport, self.context.assets, self.effects.offset)
        screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(screen)
        for entity in self.sim.entities:
            entity.draw(ctx)
        self.effects.draw_health_bars(ctx, self.sim.entities)
        # Münzen über den Gefahren: Collectibles bleiben sichtbar, auch wenn ein
        # langsamerer Gegner kurz überholt wird.
        for formation in self.sim.formations:
            formation.draw(ctx)
        for projectile in self.sim.projectiles:
            projectile.draw(ctx)
        self._draw_ghost(ctx)
        if not self.sim.is_over:
            self._draw_player(ctx)
        self.effects.draw(ctx)
        self.effects.draw_overlay(screen)
        self._draw_weapon_hud()
        self._draw_hp_hud()
        self._draw_shield_hud()
        self._draw_score()
        self._draw_difficulty_debug()
        pygame.display.flip()

    def ghost_offset_x(self) -> float:
        """Waagerechter Versatz des Ghost-Schiffs aus dem Lichtjahr-Vorsprung.

        Negativ heißt: der Spieler ist weiter, der Ghost fällt nach hinten.
        `tanh` sättigt den Versatz weich, damit ein großer Abstand den Ghost
        nicht schlagartig aus dem Bild wirft.
        """
        assert self.ghost is not None
        delta = self.ghost.delta(self.sim.light_years)
        return -GHOST_LEAD_MAX_OFFSET * math.tanh(delta / GHOST_LEAD_SOFT_LIGHT_YEARS)

    def ghost_draw_rect(self) -> pygame.Rect | None:
        """Referenz-Rechteck des Ghost-Schiffs inklusive Versatz; `None` = unsichtbar.

        Solange der Ghost lebt, bleibt er am linken Rand hängen statt zu
        verschwinden — er ist die einzige Referenz. Ist sein Lauf zu Ende,
        darf er zurückfallen und aus dem Bild fliegen.
        """
        if self.ghost is None:
            return None
        rect = self.ghost.rect.move(round(self.ghost_offset_x()), 0)
        if not self.ghost.finished:
            rect.x = max(rect.x, GHOST_LEAD_MIN_X)
            return rect
        if self._ghost_fade <= 0.0 or rect.right <= 0 or rect.left >= REFERENCE_SIZE[0]:
            return None
        return rect

    def _draw_ghost(self, ctx: RenderContext) -> None:
        """Ghost-Schiff halbtransparent, um seinen Rückstand nach hinten versetzt."""
        target_ref = self.ghost_draw_rect()
        if target_ref is None:
            return
        target = ctx.rect(target_ref)
        image = self.ghost_image(target.size)
        image.set_alpha(round(GHOST_ALPHA * self._ghost_fade))
        ctx.surface.blit(image, target)

    def _draw_player(self, ctx: RenderContext) -> None:
        """Spielerschiff an der Simulationsposition, in Fenstergröße."""
        target = ctx.rect(self.sim.player.rect)
        ctx.surface.blit(self.ship_image(target.size), target)

    def _draw_shield_hud(self) -> None:
        """`SCHILD xN` oben links, nur solange Ladungen übrig sind."""
        if self.sim.shield_charges <= 0:
            return
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        color = self._hud_color("shield", SHIELD_HUD_COLOR)
        text = font.render(f"SCHILD x{self.sim.shield_charges}", True, color)
        text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(text, text.get_rect(topleft=vp.point(*SHIELD_HUD_TOP_LEFT)))

    def _draw_hp_hud(self) -> None:
        """`HP <aktuell>/<max>` oben links."""
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        player = self.sim.player
        hp_text = font.render(
            f"HP {player.hp}/{player.max_hp}", True, self._hud_color("hp", TEXT_COLOR)
        )
        hp_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(hp_text, hp_text.get_rect(topleft=vp.point(*HP_HUD_TOP_LEFT)))

    def _draw_weapon_hud(self) -> None:
        """Aktive Waffe mit Munition oben links."""
        vp = self.context.viewport
        font = vp.font(WEAPON_HUD_FONT_SIZE)
        active = self.sim.loadout.active
        weapon_text = font.render(
            f"{active.spec.name} {active.ammo}/{active.spec.max_ammo}",
            True,
            self._hud_color("weapon", TEXT_COLOR),
        )
        weapon_text.set_alpha(SCORE_ALPHA)
        weapon_rect = weapon_text.get_rect(topleft=vp.point(*WEAPON_HUD_TOP_LEFT))
        self.context.screen.blit(weapon_text, weapon_rect)

    def _difficulty_debug_lines(self) -> tuple[str, ...]:
        active = self.sim.loadout.active
        player = self.sim.player
        difficulty = self.sim.difficulty
        return (
            (f"DEBUG {self.mode.value.upper()} {self.recorder.director_kind.value.upper()}"),
            f"TICK {self.sim.tick:06d}",
            (
                f"SPEED x{difficulty.speed_multiplier:.3f} "
                f"INTERVAL x{difficulty.spawn_interval_multiplier:.3f}"
            ),
            (f"HP {player.hp}/{player.max_hp} AMMO {active.ammo}/{active.spec.max_ammo}"),
        )

    def _draw_difficulty_debug(self) -> None:
        if not self._show_difficulty_debug:
            return
        vp = self.context.viewport
        font = vp.font(DIFFICULTY_DEBUG_HUD_FONT_SIZE)
        left, top = DIFFICULTY_DEBUG_HUD_TOP_LEFT
        for index, line in enumerate(self._difficulty_debug_lines()):
            text = font.render(line, True, DIFFICULTY_DEBUG_HUD_COLOR)
            text.set_alpha(SCORE_ALPHA)
            position = vp.point(left, top + index * DIFFICULTY_DEBUG_HUD_LINE_SPACING)
            self.context.screen.blit(text, text.get_rect(topleft=position))

    def _draw_score(self) -> None:
        """Lightyears, Münzen, Ghost-Vergleich und Bonus-Hinweis oben rechts."""
        vp = self.context.viewport
        font = vp.font(SCORE_FONT_SIZE)

        score_text = font.render(f"LIGHTYRS {self.sim.score.formatted()}", True, TEXT_COLOR)
        score_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(
            score_text, score_text.get_rect(topright=vp.point(*SCORE_TOP_RIGHT))
        )

        coins_text = font.render(
            f"COINS {format_coins(self.sim.coins_collected)}",
            True,
            self._hud_color("coins", COIN_COLOR),
        )
        coins_text.set_alpha(SCORE_ALPHA)
        self.context.screen.blit(
            coins_text, coins_text.get_rect(topright=vp.point(*COINS_TOP_RIGHT))
        )

        if self.spectate is not None:
            author = short_pubkey(self.spectate.author) if self.spectate.author else "DIR"
            replay_text = font.render(f"REPLAY VON {author}", True, GHOST_HUD_COLOR)
            replay_text.set_alpha(SCORE_ALPHA)
            self.context.screen.blit(
                replay_text, replay_text.get_rect(topright=vp.point(*GHOST_HUD_TOP_RIGHT))
            )
        elif self.ghost is not None:
            delta = self.ghost.delta(self.sim.light_years)
            sign = "+" if delta >= 0 else "-"
            ghost_text = font.render(
                f"GHOST {format_light_years(self.ghost.light_years)} {sign}{abs(delta):.0f}",
                True,
                GHOST_HUD_COLOR,
            )
            ghost_text.set_alpha(SCORE_ALPHA)
            self.context.screen.blit(
                ghost_text, ghost_text.get_rect(topright=vp.point(*GHOST_HUD_TOP_RIGHT))
            )

        if self._bonus_notice_ttl > 0:
            bonus_text = font.render(self._bonus_notice, True, COIN_COLOR)
            bonus_text.set_alpha(round(255 * self._bonus_notice_ttl / COIN_BONUS_NOTICE_SECONDS))
            self.context.screen.blit(
                bonus_text, bonus_text.get_rect(topright=vp.point(*COIN_BONUS_TOP_RIGHT))
            )
