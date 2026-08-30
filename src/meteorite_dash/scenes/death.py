import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COIN_COLOR,
    DEATH_BORDER_COLOR,
    DEATH_HIGHLIGHT_COLOR,
    DEATH_MESSAGE_FONT_SIZE,
    DEATH_MUTED_COLOR,
    DEATH_SOUND,
    DEATH_SUBTITLE_FONT_SIZE,
    DEATH_TITLE_FONT_SIZE,
    HINT_FONT_SIZE,
    SCORE_FONT_SIZE,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import format_coins, format_light_years


class DeathScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)

    def on_enter(self) -> None:
        self.context.music.play_sound_effect(DEATH_SOUND)

    def on_exit(self) -> None:
        pygame.mixer.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.finish(Transition.MAIN_MENU)
        elif event.type == pygame.QUIT:
            self.finish(Transition.QUIT)

    def draw(self) -> None:
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

        message = message_font.render("DEIN LAUF ENDET HIER", True, muted_color)
        message_rect = message.get_rect(center=(center_x, vp.py(330)))
        screen.blit(message, message_rect)

        final_score = score_font.render(
            f"DISTANZ: {format_light_years(self.context.state.final_light_years)} LICHTJAHRE",
            True,
            highlight_color,
        )
        final_score_rect = final_score.get_rect(center=(center_x, vp.py(390)))
        screen.blit(final_score, final_score_rect)

        final_coins = score_font.render(
            f"MÜNZEN: {format_coins(self.context.state.final_coins)}", True, COIN_COLOR
        )
        final_coins_rect = final_coins.get_rect(center=(center_x, vp.py(430)))
        screen.blit(final_coins, final_coins_rect)

        seed_text = hint_font.render(f"SEED {self.context.state.final_seed}", True, muted_color)
        screen.blit(seed_text, seed_text.get_rect(center=(center_x, vp.py(465))))

        hint = hint_font.render("DRÜCKE EINE BELIEBIGE TASTE", True, TEXT_COLOR)
        hint_rect = hint.get_rect(center=(center_x, vp.py(500)))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
