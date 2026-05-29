import pygame

from meteorite_dash.assets import SHIP_IMAGES
from meteorite_dash.config import (
    BACKGROUND_COLOR,
    SELECTED_TEXT_COLOR,
    SHIP_PREVIEW_SIZE,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Scene, Transition


class ShipSelection(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.previews = [
            context.assets.load_ship(filename, SHIP_PREVIEW_SIZE) for filename in SHIP_IMAGES
        ]

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        state = self.context.state
        if event.key in (pygame.K_LEFT, pygame.K_UP):
            state.selected_ship_index = (state.selected_ship_index - 1) % len(SHIP_IMAGES)
        elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
            state.selected_ship_index = (state.selected_ship_index + 1) % len(SHIP_IMAGES)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
            self.finish(Transition.MAIN_MENU)

    def draw(self) -> None:
        screen = self.context.screen
        screen.fill(BACKGROUND_COLOR)
        center_x = screen.get_width() // 2
        selected_index = self.context.state.selected_ship_index

        title = self.context.menu_font.render("Raumschiff auswählen", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(center_x, 120))
        screen.blit(title, title_rect)

        start_x = center_x - 120
        for index, preview in enumerate(self.previews):
            x = start_x + index * 240
            ship_rect = preview.get_rect(center=(x, 280))
            screen.blit(preview, ship_rect)

            color = SELECTED_TEXT_COLOR if index == selected_index else TEXT_COLOR
            label = self.context.hint_font.render(SHIP_IMAGES[index], True, color)
            label_rect = label.get_rect(center=(x, 365))
            screen.blit(label, label_rect)

            if index == selected_index:
                pygame.draw.rect(screen, SELECTED_TEXT_COLOR, ship_rect.inflate(24, 24), 3)

        hint = self.context.hint_font.render(
            "Links/Rechts: wählen  Enter/Escape: zurück", True, TEXT_COLOR
        )
        hint_rect = hint.get_rect(center=(center_x, 500))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
