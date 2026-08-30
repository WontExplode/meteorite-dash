"""Death-/Game-Over-Screen: Lightyears, Münzen, Rekordvergleich und Seed des Laufs."""

import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COIN_COLOR,
    DEATH_BORDER_COLOR,
    DEATH_HIGHLIGHT_COLOR,
    DEATH_MESSAGE_FONT_SIZE,
    DEATH_MODE_COLOR,
    DEATH_MUTED_COLOR,
    DEATH_SOUND,
    DEATH_SUBTITLE_FONT_SIZE,
    DEATH_TITLE_FONT_SIZE,
    HINT_FONT_SIZE,
    SCORE_FONT_SIZE,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.identity import short_pubkey
from meteorite_dash.replay import RunMode
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import format_coins, format_light_years


class DeathScene(Scene):
    """Game-Over-Screen nach dem Tod.

    Liest nur `GameState.final_*`; eine beliebige Taste führt zurück ins Hauptmenü.
    """

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)

    def on_enter(self) -> None:
        """Spielt den Todes-Sound."""
        self.context.music.play_sound_effect(DEATH_SOUND)

    def on_exit(self) -> None:
        """Stoppt laufende Soundeffekte."""
        pygame.mixer.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        """Jede Taste führt zurück ins Hauptmenü."""
        if event.type == pygame.KEYDOWN:
            state = self.context.state
            played = state.final_spectate_author is None
            if event.key == pygame.K_TAB and played and state.final_mode is RunMode.DAILY:
                self.finish(Transition.LEADERBOARD)
            elif event.key == pygame.K_c and self.can_share():
                self.share()
            else:
                self.finish(Transition.MAIN_MENU)
        elif event.type == pygame.QUIT:
            self.finish(Transition.QUIT)

    def draw(self) -> None:
        """Zeichnet Rahmen, Scanlines, Titel, Modus-Zeile, Score, Münzen, Rekord, Seed."""
        screen = self.context.screen
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x

        border_color = DEATH_BORDER_COLOR
        highlight_color = DEATH_HIGHLIGHT_COLOR
        muted_color = DEATH_MUTED_COLOR

        scanline_gap = max(1, vp.s(8))
        for y in range(0, vp.height, scanline_gap):
            pygame.draw.line(screen, (18, 18, 32), (0, y), (vp.width, y))

        border_rect = pygame.Rect(
            vp.px(55),
            vp.py(55),
            vp.px(745) - vp.px(55),
            vp.py(545) - vp.py(55),
        )
        inner_rect = pygame.Rect(
            vp.px(70),
            vp.py(70),
            vp.px(730) - vp.px(70),
            vp.py(530) - vp.py(70),
        )
        pygame.draw.rect(screen, border_color, border_rect, max(1, vp.s(4)))
        pygame.draw.rect(screen, muted_color, inner_rect, max(1, vp.s(2)))

        title_font = vp.font(DEATH_TITLE_FONT_SIZE)
        subtitle_font = vp.font(DEATH_SUBTITLE_FONT_SIZE)
        message_font = vp.font(DEATH_MESSAGE_FONT_SIZE)
        score_font = vp.font(SCORE_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        shadow = title_font.render("GAME OVER", True, (80, 0, 0))
        shadow_rect = shadow.get_rect(center=(center_x + vp.s(5), vp.py(170) + vp.s(5)))
        screen.blit(shadow, shadow_rect)

        title = title_font.render("GAME OVER", True, border_color)
        title_rect = title.get_rect(center=(center_x, vp.py(170)))
        screen.blit(title, title_rect)

        subtitle = subtitle_font.render("SCHIFF ZERSTÖRT", True, highlight_color)
        subtitle_rect = subtitle.get_rect(center=(center_x, vp.py(260)))
        screen.blit(subtitle, subtitle_rect)

        state = self.context.state
        if state.final_spectate_author is not None:
            author = short_pubkey(state.final_spectate_author) or "DIR"
            message = message_font.render(f"REPLAY VON {author}", True, DEATH_MODE_COLOR)
        elif state.final_mode is RunMode.DAILY:
            message = message_font.render(f"DAILY RUN {state.final_label}", True, DEATH_MODE_COLOR)
        else:
            message = message_font.render("DEIN LAUF ENDET HIER", True, muted_color)
        screen.blit(message, message.get_rect(center=(center_x, vp.py(330))))

        final_score = score_font.render(
            f"DISTANZ: {format_light_years(state.final_light_years)} LICHTJAHRE",
            True,
            highlight_color,
        )
        screen.blit(final_score, final_score.get_rect(center=(center_x, vp.py(380))))

        final_coins = score_font.render(
            f"MÜNZEN: {format_coins(state.final_coins)}", True, COIN_COLOR
        )
        screen.blit(final_coins, final_coins.get_rect(center=(center_x, vp.py(408))))

        record_line, record_color = self._record_line()
        if record_line:
            record_text = score_font.render(record_line, True, record_color)
            screen.blit(record_text, record_text.get_rect(center=(center_x, vp.py(436))))

        seed_text = hint_font.render(f"SEED {state.final_seed}", True, muted_color)
        screen.blit(seed_text, seed_text.get_rect(center=(center_x, vp.py(462))))

        share_line = self._share_line()
        if share_line:
            share_text = hint_font.render(share_line, True, DEATH_MODE_COLOR)
            screen.blit(share_text, share_text.get_rect(center=(center_x, vp.py(486))))

        hint = hint_font.render(self._hint_line(), True, TEXT_COLOR)
        screen.blit(hint, hint.get_rect(center=(center_x, vp.py(512))))

        pygame.display.flip()

    def _record_line(self) -> tuple[str, tuple[int, int, int]]:
        """Vergleich mit dem Ghost-Rekord zum selben Seed; leer ohne Vergleich."""
        state = self.context.state
        record = state.final_record_light_years
        if record is None:
            return "", DEATH_MUTED_COLOR
        # Fremder Rekord (Community-Ghost) trägt die Kurzform seines Pubkeys.
        holder = (
            f" VON {short_pubkey(state.final_record_author)}" if state.final_record_author else ""
        )
        if state.final_light_years > record:
            return (
                f"NEUER REKORD (VORHER {format_light_years(record)}{holder})",
                DEATH_HIGHLIGHT_COLOR,
            )
        delta = round(state.final_light_years - record)
        return f"REKORD {format_light_years(record)}{holder} ({delta:+d})", DEATH_MUTED_COLOR

    def _share_line(self) -> str:
        """Stand des Teilens (Nostr): Code-Teilen vor Rekord-Teilen; leer ohne beides."""
        exchange = self.context.exchange
        if exchange is None:
            return ""
        return exchange.share_status or exchange.publish_status

    def _hint_line(self) -> str:
        state = self.context.state
        if state.final_spectate_author is not None:
            return "TASTE: MENÜ"
        parts = ["TASTE: MENÜ"]
        if state.final_mode is RunMode.DAILY:
            parts.append("TAB: BESTENLISTE")
        if self.can_share():
            parts.append("C: CODE TEILEN")
        return "   ".join(parts)

    def can_share(self) -> bool:
        state = self.context.state
        return (
            self.context.exchange is not None
            and state.last_replay is not None
            and state.final_spectate_author is None
        )

    def share(self) -> None:
        """`C`: den gerade beendeten Lauf unter seiner Phrase veröffentlichen."""
        exchange = self.context.exchange
        replay = self.context.state.last_replay
        if exchange is not None and replay is not None and self.can_share():
            exchange.share(replay)
