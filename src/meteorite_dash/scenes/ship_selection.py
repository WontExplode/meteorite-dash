import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    REFERENCE_SIZE,
    SELECTED_TEXT_COLOR,
    SHIP_PREVIEW_SIZE,
    STAT_BAR_COLOR,
    TEXT_COLOR,
)
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.ships import SHIPS, ShipSpec


class ShipSelection(Scene):
    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        state = self.context.state
        if event.key in (pygame.K_LEFT, pygame.K_UP):
            state.selected_ship_index = (state.selected_ship_index - 1) % len(SHIPS)
        elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
            state.selected_ship_index = (state.selected_ship_index + 1) % len(SHIPS)
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
        title_rect = title.get_rect(center=(center_x, vp.py(80)))
        screen.blit(title, title_rect)

        preview_size = (vp.s(SHIP_PREVIEW_SIZE[0]), vp.s(SHIP_PREVIEW_SIZE[1]))
        spacing = REFERENCE_SIZE[0] / len(SHIPS)
        for index, spec in enumerate(SHIPS):
            preview = self.context.assets.load_ship(spec.sprite, preview_size, spec.tint)
            x = vp.px(spacing / 2 + index * spacing)
            ship_rect = preview.get_rect(center=(x, vp.py(200)))
            screen.blit(preview, ship_rect)

            color = SELECTED_TEXT_COLOR if index == selected_index else TEXT_COLOR
            label = hint_font.render(spec.name, True, color)
            label_rect = label.get_rect(center=(x, vp.py(272)))
            screen.blit(label, label_rect)

            if index == selected_index:
                box = ship_rect.inflate(vp.s(20), vp.s(20))
                pygame.draw.rect(screen, SELECTED_TEXT_COLOR, box, 3)

        self._draw_stats(SHIPS[selected_index])

        hint = hint_font.render("Links/Rechts: wählen  Enter/Escape: zurück", True, TEXT_COLOR)
        hint_rect = hint.get_rect(center=(center_x, vp.py(545)))
        screen.blit(hint, hint_rect)

        pygame.display.flip()

    def _draw_stats(self, spec: ShipSpec) -> None:
        """Zeichnet die abgeleiteten Werte des gewählten Schiffs als Balken,
        normiert auf das jeweilige Flottenmaximum."""
        screen = self.context.screen
        vp = self.context.viewport
        hint_font = vp.font(HINT_FONT_SIZE)
        rows = (
            ("Tempo", spec.max_speed, max(s.max_speed for s in SHIPS)),
            ("Reaktion", spec.agility, max(s.agility for s in SHIPS)),
            ("Hülle", float(spec.hp), max(float(s.hp) for s in SHIPS)),
        )
        for row, (label_text, value, fleet_max) in enumerate(rows):
            y = vp.py(340 + row * 36)
            label = hint_font.render(label_text, True, TEXT_COLOR)
            screen.blit(label, label.get_rect(midleft=(vp.px(220), y)))

            bar = pygame.Rect(vp.px(340), y - vp.s(8), vp.s(260), vp.s(16))
            pygame.draw.rect(screen, STAT_BAR_COLOR, bar)
            fill = bar.copy()
            fill.width = round(bar.width * value / fleet_max)
            pygame.draw.rect(screen, SELECTED_TEXT_COLOR, fill)

        slots = hint_font.render(
            f"Waffenplätze: {spec.weapon_slots}   Zubehörplätze: {spec.accessory_slots}",
            True,
            TEXT_COLOR,
        )
        slots_rect = slots.get_rect(center=(vp.center_x, vp.py(340 + len(rows) * 36)))
        screen.blit(slots, slots_rect)
