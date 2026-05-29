import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    MENU_ITEMS,
    SELECTED_TEXT_COLOR,
    TEXT_COLOR,
    MenuAction,
)
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Scene, Transition

_ACTION_TRANSITIONS: dict[MenuAction, Transition] = {
    "start": Transition.START_GAME,
    "ship": Transition.SHIP_SELECTION,
    "quit": Transition.QUIT,
}


class MainMenu(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.selected_index = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_UP:
            self.selected_index = (self.selected_index - 1) % len(MENU_ITEMS)
        elif event.key == pygame.K_DOWN:
            self.selected_index = (self.selected_index + 1) % len(MENU_ITEMS)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            action = MENU_ITEMS[self.selected_index][1]
            self.finish(_ACTION_TRANSITIONS[action])

    def draw(self) -> None:
        screen = self.context.screen
        screen.fill(BACKGROUND_COLOR)
        center_x = screen.get_width() // 2

        title = self.context.menu_font.render("Meteorite Dash", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(center_x, 120))
        screen.blit(title, title_rect)

        for index, (label, _) in enumerate(MENU_ITEMS):
            color = SELECTED_TEXT_COLOR if index == self.selected_index else TEXT_COLOR
            text = self.context.menu_font.render(label, True, color)
            text_rect = text.get_rect(center=(center_x, 240 + index * 70))
            screen.blit(text, text_rect)

        selected_ship = self.context.hint_font.render(
            f"Ausgewählt: {self.context.state.selected_ship_filename}", True, TEXT_COLOR
        )
        selected_ship_rect = selected_ship.get_rect(center=(center_x, 500))
        screen.blit(selected_ship, selected_ship_rect)

        hint = self.context.hint_font.render(
            "Pfeiltasten: wählen  Enter: bestätigen", True, TEXT_COLOR
        )
        hint_rect = hint.get_rect(center=(center_x, 535))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
