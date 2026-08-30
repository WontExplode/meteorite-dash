import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COMMUNITY_STATUS_COLOR,
    COMMUNITY_STATUS_TOP,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    MENU_HINT_TOP,
    MENU_ITEM_FONT_SIZE,
    MENU_ITEM_SPACING,
    MENU_ITEMS,
    MENU_ITEMS_TOP,
    MENU_SELECTED_SHIP_TOP,
    SELECTED_TEXT_COLOR,
    TEXT_COLOR,
    MenuAction,
)
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.widgets import draw_wallet

_ACTION_TRANSITIONS: dict[MenuAction, Transition] = {
    "start": Transition.START_GAME,
    "daily": Transition.START_DAILY,
    "leaderboard": Transition.LEADERBOARD,
    "code": Transition.CODE_ENTRY,
    "ship": Transition.SHIP_SELECTION,
    "shop": Transition.SHOP,
    "quit": Transition.QUIT,
}


class MainMenu(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.selected_index = 0

    def on_enter(self) -> None:
        # Läufe zum Tages-Seed schon im Menü holen: beim Start sind sie meist da.
        if self.context.exchange is not None:
            self.context.exchange.prefetch(daily_seed(today_utc()))

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
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x
        menu_font = vp.font(MENU_FONT_SIZE)
        item_font = vp.font(MENU_ITEM_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = menu_font.render("Meteorite Dash", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(center_x, vp.py(120)))
        screen.blit(title, title_rect)

        for index, (label, _) in enumerate(MENU_ITEMS):
            color = SELECTED_TEXT_COLOR if index == self.selected_index else TEXT_COLOR
            text = item_font.render(label, True, color)
            text_rect = text.get_rect(
                center=(center_x, vp.py(MENU_ITEMS_TOP + index * MENU_ITEM_SPACING))
            )
            screen.blit(text, text_rect)

        if self.context.exchange is not None and self.context.exchange.status:
            status = hint_font.render(self.context.exchange.status, True, COMMUNITY_STATUS_COLOR)
            screen.blit(status, status.get_rect(center=(center_x, vp.py(COMMUNITY_STATUS_TOP))))

        selected_ship = hint_font.render(
            f"Ausgewählt: {self.context.state.selected_ship.name}", True, TEXT_COLOR
        )
        selected_ship_rect = selected_ship.get_rect(
            center=(center_x, vp.py(MENU_SELECTED_SHIP_TOP))
        )
        screen.blit(selected_ship, selected_ship_rect)

        hint = hint_font.render("Pfeiltasten: wählen  Enter: bestätigen", True, TEXT_COLOR)
        hint_rect = hint.get_rect(center=(center_x, vp.py(MENU_HINT_TOP)))
        screen.blit(hint, hint_rect)

        draw_wallet(self.context)
        pygame.display.flip()
