import pygame

from meteorite_dash.config import BACKGROUND_COLOR, DEATH_SOUND, TEXT_COLOR
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Scene, Transition


class DeathScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)

    def on_enter(self) -> None:
        self.context.music.play_sound_effect(DEATH_SOUND)

    def on_exit(self) -> None:
        self.context.music.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.finish(Transition.MAIN_MENU)
        elif event.type == pygame.QUIT:
            self.finish(Transition.QUIT)

    def draw(self) -> None:
        screen = self.context.screen
        screen.fill(BACKGROUND_COLOR)
        center_x = screen.get_width() // 2

        border_color = (255, 80, 80)
        highlight_color = (255, 210, 80)
        muted_color = (120, 120, 150)

        for y in range(0, screen.get_height(), 8):
            pygame.draw.line(screen, (18, 18, 32), (0, y), (screen.get_width(), y))

        pygame.draw.rect(screen, border_color, (55, 55, screen.get_width() - 110, 490), 4)
        pygame.draw.rect(screen, muted_color, (70, 70, screen.get_width() - 140, 460), 2)

        title_font = pygame.font.SysFont("consolas", 84, bold=True)
        subtitle_font = pygame.font.SysFont("consolas", 28, bold=True)
        message_font = pygame.font.SysFont("consolas", 24)
        hint_font = pygame.font.SysFont("consolas", 22)

        shadow = title_font.render("GAME OVER", True, (80, 0, 0))
        shadow_rect = shadow.get_rect(center=(center_x + 5, 170 + 5))
        screen.blit(shadow, shadow_rect)

        title = title_font.render("GAME OVER", True, border_color)
        title_rect = title.get_rect(center=(center_x, 170))
        screen.blit(title, title_rect)

        subtitle = subtitle_font.render("SHIP DESTROYED", True, highlight_color)
        subtitle_rect = subtitle.get_rect(center=(center_x, 260))
        screen.blit(subtitle, subtitle_rect)

        message = message_font.render("YOUR RUN ENDS HERE", True, muted_color)
        message_rect = message.get_rect(center=(center_x, 330))
        screen.blit(message, message_rect)

        hint = hint_font.render("PRESS ANY KEY TO RETURN TO MENU", True, TEXT_COLOR)
        hint_rect = hint.get_rect(center=(center_x, 500))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
