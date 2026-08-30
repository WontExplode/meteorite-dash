"""Schiffsauswahl: Cursor über `SHIPS`, Stat-Balken, Übernahme nur freier Schiffe."""

import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COIN_COLOR,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    MUTED_TEXT_COLOR,
    OWNED_TEXT_COLOR,
    REFERENCE_SIZE,
    SELECTED_TEXT_COLOR,
    SHIP_PREVIEW_SIZE,
    SHOP_FEEDBACK_SECONDS,
    STAT_BAR_COLOR,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.widgets import dimmed, draw_wallet
from meteorite_dash.ships import SHIPS, ShipSpec


class ShipSelection(Scene):
    """Schiffsauswahl.

    Der Cursor läuft über alle Schiffe — auch gesperrte, damit man ihre Werte
    ansehen kann. Übernommen (`GameState.selected_ship_index`) wird nur ein
    freigeschaltetes Schiff; gekauft wird im Shop.
    """

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.cursor = context.state.selected_ship_index
        self._feedback = ""
        self._feedback_ttl = 0.0

    @property
    def highlighted(self) -> ShipSpec:
        """Schiff unter dem Cursor (auch gesperrt)."""
        return SHIPS[self.cursor]

    def handle_event(self, event: pygame.event.Event) -> None:
        """Pfeiltasten bewegen den Cursor, Enter übernimmt, Escape geht zurück."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_LEFT, pygame.K_UP):
            self.cursor = (self.cursor - 1) % len(SHIPS)
        elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
            self.cursor = (self.cursor + 1) % len(SHIPS)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._confirm()
        elif event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)

    def _confirm(self) -> None:
        """Übernimmt ein freigeschaltetes Schiff; bei gesperrtem Hinweis auf den Shop."""
        spec = self.highlighted
        if self.context.state.progress.is_ship_unlocked(spec):
            self.context.state.selected_ship_index = self.cursor
            self.finish(Transition.MAIN_MENU)
            return
        self._feedback = f"Gesperrt — im Shop für {spec.price} Münzen kaufen"
        self._feedback_ttl = SHOP_FEEDBACK_SECONDS

    def update(self, dt: float) -> None:
        """Lässt den Hinweis-Text ablaufen (Wandzeit, reine Deko)."""
        self._feedback_ttl = max(0.0, self._feedback_ttl - dt)

    def draw(self) -> None:
        """Zeichnet alle Schiffe mit Name, Status, Cursor-Rahmen, Stat-Balken und Wallet."""
        screen = self.context.screen
        vp = self.context.viewport
        state = self.context.state
        progress = state.progress
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x
        menu_font = vp.font(MENU_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = menu_font.render("Raumschiff auswählen", True, TEXT_COLOR)
        title_rect = title.get_rect(center=(center_x, vp.py(80)))
        screen.blit(title, title_rect)

        preview_size = (vp.s(SHIP_PREVIEW_SIZE[0]), vp.s(SHIP_PREVIEW_SIZE[1]))
        spacing = REFERENCE_SIZE[0] / len(SHIPS)
        for index, spec in enumerate(SHIPS):
            unlocked = progress.is_ship_unlocked(spec)
            preview = self.context.assets.load_ship(
                spec.sprite, preview_size, progress.ship_tint(spec)
            )
            if not unlocked:
                preview = dimmed(preview)
            x = vp.px(spacing / 2 + index * spacing)
            ship_rect = preview.get_rect(center=(x, vp.py(200)))
            screen.blit(preview, ship_rect)

            if index == self.cursor:
                color = SELECTED_TEXT_COLOR
            elif unlocked:
                color = TEXT_COLOR
            else:
                color = MUTED_TEXT_COLOR
            label = hint_font.render(spec.name, True, color)
            label_rect = label.get_rect(center=(x, vp.py(272)))
            screen.blit(label, label_rect)

            if not unlocked:
                sub = hint_font.render(f"{spec.price} Münzen", True, COIN_COLOR)
            elif index == state.selected_ship_index:
                sub = hint_font.render("Aktiv", True, OWNED_TEXT_COLOR)
            else:
                sub = None
            if sub is not None:
                screen.blit(sub, sub.get_rect(center=(x, vp.py(296))))

            if index == self.cursor:
                box = ship_rect.inflate(vp.s(20), vp.s(20))
                pygame.draw.rect(screen, SELECTED_TEXT_COLOR, box, 3)

        self._draw_stats(self.highlighted)

        if self._feedback_ttl > 0:
            feedback = hint_font.render(self._feedback, True, SELECTED_TEXT_COLOR)
            screen.blit(feedback, feedback.get_rect(center=(center_x, vp.py(510))))

        hint = hint_font.render(
            "Links/Rechts: wählen  Enter: übernehmen  Escape: zurück", True, TEXT_COLOR
        )
        hint_rect = hint.get_rect(center=(center_x, vp.py(545)))
        screen.blit(hint, hint_rect)

        draw_wallet(self.context)
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
