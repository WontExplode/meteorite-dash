"""Hauptmenü im Endgame-Look: Sternenfeld, Scanlines, Rahmen und Deko-Action.

Einträge kommen aus `MENU_ITEMS`, Aktionen aus `_ACTION_TRANSITIONS`. Die
Deko (`MenuFX`) ist reines Rendering: Meteoriten prallen von Titel und
Menüpunkten ab, Deko-Gegner schießen sie ab.
"""

import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COMMUNITY_STATUS_COLOR,
    COMMUNITY_STATUS_TOP,
    HINT_FONT_SIZE,
    MENU_BORDER_COLOR,
    MENU_BORDER_INNER_COLOR,
    MENU_BORDER_INNER_RECT,
    MENU_BORDER_RECT,
    MENU_FONT_NAME,
    MENU_HINT_TOP,
    MENU_ITEM_FONT_SIZE,
    MENU_ITEM_TOPS,
    MENU_ITEMS,
    MENU_SCANLINE_COLOR,
    MENU_SCANLINE_GAP,
    MENU_SELECTED_SHIP_TOP,
    MENU_TITLE_FONT_SIZE,
    MENU_TITLE_SHADOW_COLOR,
    MENU_TITLE_TOP,
    MUTED_TEXT_COLOR,
    REFERENCE_SIZE,
    SELECTED_TEXT_COLOR,
    TEXT_COLOR,
    MenuAction,
)
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.menu_fx import MenuFX
from meteorite_dash.render import RenderContext
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

_TITLE_TEXT = "METEORITE DASH"


class MainMenu(Scene):
    """Hauptmenü mit Cursor über `MENU_ITEMS`; Enter löst den passenden `Transition` aus."""

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.selected_index = 0
        # Ziel-Rechtecke (Titel + Menüpunkte) im Referenzraum für die Abpraller.
        self.fx = MenuFX(self._collision_targets())

    def _collision_targets(self) -> list[pygame.Rect]:
        """Buchstaben-Rechtecke von Titel und Menüpunkten (Index 0 = Titel).

        Gemessen im Referenzraum — damit fensterunabhängig; die Auslenkungen
        aus `MenuFX` skaliert erst das Zeichnen.
        """
        title_font = pygame.font.SysFont(MENU_FONT_NAME, MENU_TITLE_FONT_SIZE)
        item_font = pygame.font.SysFont(MENU_FONT_NAME, MENU_ITEM_FONT_SIZE)
        center_x = REFERENCE_SIZE[0] // 2
        targets = [self._ink_rect(title_font, _TITLE_TEXT, center_x, MENU_TITLE_TOP)]
        for index, (label, _) in enumerate(MENU_ITEMS):
            targets.append(
                self._ink_rect(item_font, label.upper(), center_x, MENU_ITEM_TOPS[index])
            )
        return targets

    @staticmethod
    def _ink_rect(font: pygame.font.Font, text: str, center_x: int, center_y: int) -> pygame.Rect:
        """Sichtbare Buchstaben-Box eines zentrierten Texts (Referenzraum).

        `font.size` liefert die volle Zeilenhöhe inklusive Ober-/Unterlängen-
        Reserve — Meteoriten würden scheinbar in Luft abprallen. Deshalb wird
        das gerenderte Bild auf die Tinte beschnitten (`get_bounding_rect`).
        """
        rendered = font.render(text, True, TEXT_COLOR)
        surface_rect = rendered.get_rect(center=(center_x, center_y))
        return rendered.get_bounding_rect().move(surface_rect.left, surface_rect.top)

    def on_enter(self) -> None:
        # Läufe zum Tages-Seed schon im Menü holen: beim Start sind sie meist da.
        if self.context.exchange is not None:
            self.context.exchange.prefetch(daily_seed(today_utc()))

    def handle_event(self, event: pygame.event.Event) -> None:
        """Pfeiltasten bewegen den Cursor zyklisch, Enter/Leertaste bestätigen."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_UP:
            self.selected_index = (self.selected_index - 1) % len(MENU_ITEMS)
        elif event.key == pygame.K_DOWN:
            self.selected_index = (self.selected_index + 1) % len(MENU_ITEMS)
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            action = MENU_ITEMS[self.selected_index][1]
            self.finish(_ACTION_TRANSITIONS[action])

    def update(self, dt: float) -> None:
        """Rückt Sternenfeld und Deko mit Wandzeit vor (reines Rendering)."""
        self.context.starfield.update(dt)
        self.fx.update(dt)

    def draw(self) -> None:
        """Zeichnet Hintergrund, Deko, Rahmen, Titel, Menü, Statuszeilen und Wallet."""
        screen = self.context.screen
        vp = self.context.viewport
        ctx = RenderContext(screen, vp, self.context.assets)
        screen.fill(BACKGROUND_COLOR)
        self.context.starfield.draw(screen)
        self._draw_scanlines()
        self.fx.draw(ctx)
        self._draw_frame()
        self._draw_title()
        self._draw_items()
        self._draw_status_lines()
        draw_wallet(self.context)
        pygame.display.flip()

    def _draw_scanlines(self) -> None:
        """CRT-Scanlines über den Hintergrund — derselbe Look wie der Death-Screen."""
        vp = self.context.viewport
        gap = max(1, vp.s(MENU_SCANLINE_GAP))
        for y in range(0, vp.height, gap):
            pygame.draw.line(self.context.screen, MENU_SCANLINE_COLOR, (0, y), (vp.width, y))

    def _frame_rect(self, ref: tuple[int, int, int, int]) -> pygame.Rect:
        """Referenz-Rechteck (x, y, Breite, Höhe) in Fensterpixel übersetzen."""
        vp = self.context.viewport
        x, y, width, height = ref
        return pygame.Rect(
            vp.px(x), vp.py(y), vp.px(x + width) - vp.px(x), vp.py(y + height) - vp.py(y)
        )

    def _draw_frame(self) -> None:
        """Doppelter Rahmen um den Bildschirm (Endgame-Look)."""
        vp = self.context.viewport
        screen = self.context.screen
        pygame.draw.rect(
            screen, MENU_BORDER_COLOR, self._frame_rect(MENU_BORDER_RECT), max(1, vp.s(3))
        )
        pygame.draw.rect(
            screen,
            MENU_BORDER_INNER_COLOR,
            self._frame_rect(MENU_BORDER_INNER_RECT),
            max(1, vp.s(1)),
        )

    def _draw_title(self) -> None:
        """Titel mit Schlagschatten; folgt der Auslenkung seines Abpraller-Ziels."""
        vp = self.context.viewport
        font = vp.font(MENU_TITLE_FONT_SIZE)
        offset_x, offset_y = self.fx.targets[0].offset
        center = (vp.center_x + vp.s(offset_x), vp.py(MENU_TITLE_TOP + offset_y))
        shadow = font.render(_TITLE_TEXT, True, MENU_TITLE_SHADOW_COLOR)
        self.context.screen.blit(
            shadow, shadow.get_rect(center=(center[0] + vp.s(4), center[1] + vp.s(4)))
        )
        title = font.render(_TITLE_TEXT, True, SELECTED_TEXT_COLOR)
        self.context.screen.blit(title, title.get_rect(center=center))

    def _draw_items(self) -> None:
        """Menüpunkte in Großbuchstaben; der gewählte bekommt Marker und Goldton."""
        vp = self.context.viewport
        font = vp.font(MENU_ITEM_FONT_SIZE)
        for index, (label, _) in enumerate(MENU_ITEMS):
            selected = index == self.selected_index
            text_value = f"> {label.upper()} <" if selected else label.upper()
            color = SELECTED_TEXT_COLOR if selected else TEXT_COLOR
            offset_x, offset_y = self.fx.targets[index + 1].offset
            center = (
                vp.center_x + vp.s(offset_x),
                vp.py(MENU_ITEM_TOPS[index] + offset_y),
            )
            text = font.render(text_value, True, color)
            self.context.screen.blit(text, text.get_rect(center=center))

    def _draw_status_lines(self) -> None:
        """Community-Status, gewähltes Schiff und Tastenhinweis unter dem Menü."""
        screen = self.context.screen
        vp = self.context.viewport
        center_x = vp.center_x
        hint_font = vp.font(HINT_FONT_SIZE)

        if self.context.exchange is not None and self.context.exchange.status:
            status = hint_font.render(self.context.exchange.status, True, COMMUNITY_STATUS_COLOR)
            screen.blit(status, status.get_rect(center=(center_x, vp.py(COMMUNITY_STATUS_TOP))))

        ship_name = self.context.state.selected_ship.name.upper()
        selected_ship = hint_font.render(f"SCHIFF: {ship_name}", True, TEXT_COLOR)
        screen.blit(
            selected_ship, selected_ship.get_rect(center=(center_x, vp.py(MENU_SELECTED_SHIP_TOP)))
        )

        hint = hint_font.render("PFEILTASTEN: WÄHLEN   ENTER: BESTÄTIGEN", True, MUTED_TEXT_COLOR)
        screen.blit(hint, hint.get_rect(center=(center_x, vp.py(MENU_HINT_TOP))))
