import pygame

from meteorite_dash.assets import SHIP_IMAGES
from meteorite_dash.config import (
    BACKGROUND_COLOR,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    SELECTED_TEXT_COLOR,
    SHIP_PREVIEW_SIZE,
    TEXT_COLOR,
)
from meteorite_dash.scenes.base import Scene, Transition


class ShipSelection(Scene):
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
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x
        selected_index = self.context.state.selected_ship_index
        menu_font = vp.font(MENU_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = menu_font.render("Raumschiff auswählen", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(center_x, vp.py(120)))
        screen.blit(title, title_rect)

        preview_size = (vp.s(SHIP_PREVIEW_SIZE[0]), vp.s(SHIP_PREVIEW_SIZE[1]))
        visible_slots = (
            (selected_index - 1) % len(SHIP_IMAGES),
            selected_index,
            (selected_index + 1) % len(SHIP_IMAGES),
        )
        slot_offsets = (-180, 0, 180)
        for slot_index, index in enumerate(visible_slots):
            filename = SHIP_IMAGES[index]
            preview = self.context.assets.load_ship(filename, preview_size)
            x = center_x + vp.px(slot_offsets[slot_index])
            ship_rect = preview.get_rect(center=(x, vp.py(280)))
            screen.blit(preview, ship_rect)

            color = SELECTED_TEXT_COLOR if index == selected_index else TEXT_COLOR
            label = hint_font.render(filename, True, color)
            label_rect = label.get_rect(center=(x, vp.py(365)))
            screen.blit(label, label_rect)

            if index == selected_index:
                box = ship_rect.inflate(vp.s(24), vp.s(24))
                pygame.draw.rect(screen, SELECTED_TEXT_COLOR, box, 3)

        counter = hint_font.render(f"{selected_index + 1} / {len(SHIP_IMAGES)}", True, TEXT_COLOR)
        counter_rect = counter.get_rect(center=(center_x, vp.py(425)))
        screen.blit(counter, counter_rect)

        hint = hint_font.render("Links/Rechts: wählen  Enter/Escape: zurück", True, TEXT_COLOR)
        hint_rect = hint.get_rect(center=(center_x, vp.py(500)))
        screen.blit(hint, hint_rect)

        pygame.display.flip()
