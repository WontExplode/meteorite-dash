"""Shop-Szene (Issue #14): Münzen gegen Schiffe, Zubehör und Farben.

Drei Reiter (Links/Rechts), Zeilen (Hoch/Runter), Enter kauft bzw. rüstet aus.
Alle Regeln (Preis, Besitz, Slot-Limit) liegen in `Progress`; die Szene
übersetzt nur `ShopResult` in Text und speichert nach jeder Änderung.
"""

from dataclasses import dataclass
from enum import Enum

import pygame

from meteorite_dash.accessories import ACCESSORIES, AccessorySpec
from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COIN_COLOR,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    MUTED_TEXT_COLOR,
    OWNED_TEXT_COLOR,
    SELECTED_TEXT_COLOR,
    SHIP_PREVIEW_SIZE,
    SHOP_FEEDBACK_SECONDS,
    SHOP_TAB_FONT_SIZE,
    TEXT_COLOR,
    Color,
)
from meteorite_dash.context import GameContext
from meteorite_dash.progress import Progress, ShopResult
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.widgets import dimmed, draw_wallet
from meteorite_dash.ships import SHIPS, TINTS, ShipSpec, TintSpec


class ShopTab(Enum):
    SHIPS = "Schiffe"
    ACCESSORIES = "Zubehör"
    TINTS = "Farben"


TABS: tuple[ShopTab, ...] = tuple(ShopTab)

# Layout im Referenzraum 800x600.
_TITLE_Y = 60
_TAB_Y = 120
_TAB_XS = (200, 400, 600)
_ROW_TOP = 180
_ROW_STEP = 42
_ROW_LEFT_X = 110
_ROW_RIGHT_X = 540
_MARKER_X = 90
_PREVIEW_CENTER = (690, 240)
_PREVIEW_NAME_Y = 300
_PREVIEW_SLOTS_Y = 326
_DESCRIPTION_Y = 455
_FEEDBACK_Y = 490
_HINT_YS = (525, 555)


@dataclass(frozen=True)
class ShopRow:
    label: str
    status: str
    status_color: Color
    description: str


class ShopScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.tab_index = 0
        self.row_index = 0
        self._feedback = ""
        self._feedback_ttl = 0.0

    @property
    def tab(self) -> ShopTab:
        return TABS[self.tab_index]

    @property
    def _progress(self) -> Progress:
        return self.context.state.progress

    @property
    def _ship(self) -> ShipSpec:
        return self.context.state.selected_ship

    def _row_count(self) -> int:
        if self.tab is ShopTab.SHIPS:
            return len(SHIPS)
        if self.tab is ShopTab.ACCESSORIES:
            return len(ACCESSORIES)
        return len(TINTS) + 1  # Zeile 0 = Standardfarbe

    # --- Eingabe ---------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_LEFT:
            self._switch_tab(-1)
        elif event.key == pygame.K_RIGHT:
            self._switch_tab(1)
        elif event.key == pygame.K_UP:
            self.row_index = (self.row_index - 1) % self._row_count()
        elif event.key == pygame.K_DOWN:
            self.row_index = (self.row_index + 1) % self._row_count()
        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._activate()
        elif event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)

    def _switch_tab(self, step: int) -> None:
        self.tab_index = (self.tab_index + step) % len(TABS)
        self.row_index = 0

    def update(self, dt: float) -> None:
        self._feedback_ttl = max(0.0, self._feedback_ttl - dt)

    def _show(self, message: str) -> None:
        self._feedback = message
        self._feedback_ttl = SHOP_FEEDBACK_SECONDS

    def _activate(self) -> None:
        if self.tab is ShopTab.SHIPS:
            self._activate_ship(SHIPS[self.row_index])
        elif self.tab is ShopTab.ACCESSORIES:
            self._activate_accessory(ACCESSORIES[self.row_index])
        elif self.row_index == 0:
            self._progress.apply_tint(self._ship, None)
            self._show(f"Standardfarbe für {self._ship.name}")
            self.context.save_progress()
        else:
            self._activate_tint(TINTS[self.row_index - 1])

    def _activate_ship(self, spec: ShipSpec) -> None:
        index = SHIPS.index(spec)
        if self._progress.is_ship_unlocked(spec):
            self.context.state.selected_ship_index = index
            self._show(f"{spec.name} ausgewählt")
            return
        result = self._progress.buy_ship(spec)
        if result is ShopResult.OK:
            self.context.state.selected_ship_index = index
            self._show(f"Gekauft: {spec.name}")
            self.context.save_progress()
        else:
            self._show(_failure_text(result, spec.name, spec.price, self._ship))

    def _activate_accessory(self, spec: AccessorySpec) -> None:
        ship = self._ship
        if not self._progress.owns_accessory(spec):
            result = self._progress.buy_accessory(spec)
            if result is not ShopResult.OK:
                self._show(_failure_text(result, spec.name, spec.price, ship))
                return
            # Bequemlichkeit: direkt ausrüsten, wenn ein Platz frei ist.
            if self._progress.toggle_accessory(ship, spec) is ShopResult.OK:
                self._show(f"Gekauft: {spec.name} — ausgerüstet auf {ship.name}")
            else:
                self._show(f"Gekauft: {spec.name}")
            self.context.save_progress()
            return
        result = self._progress.toggle_accessory(ship, spec)
        if result is ShopResult.OK:
            if self._progress.is_equipped(ship, spec):
                self._show(f"{spec.name} ausgerüstet auf {ship.name}")
            else:
                self._show(f"{spec.name} abgelegt")
            self.context.save_progress()
        else:
            self._show(_failure_text(result, spec.name, spec.price, ship))

    def _activate_tint(self, spec: TintSpec) -> None:
        ship = self._ship
        if not self._progress.owns_tint(spec):
            result = self._progress.buy_tint(spec)
            if result is not ShopResult.OK:
                self._show(_failure_text(result, spec.name, spec.price, ship))
                return
            self._progress.apply_tint(ship, spec)
            self._show(f"Gekauft: {spec.name} — aktiv auf {ship.name}")
        else:
            self._progress.apply_tint(ship, spec)
            self._show(f"{spec.name} aktiv auf {ship.name}")
        self.context.save_progress()

    # --- Zeilen ----------------------------------------------------------------

    def rows(self) -> list[ShopRow]:
        if self.tab is ShopTab.SHIPS:
            return [self._ship_row(spec) for spec in SHIPS]
        if self.tab is ShopTab.ACCESSORIES:
            return [self._accessory_row(spec) for spec in ACCESSORIES]
        return [self._default_tint_row(), *(self._tint_row(spec) for spec in TINTS)]

    def _ship_row(self, spec: ShipSpec) -> ShopRow:
        description = (
            f"Hülle {spec.hp}   Waffenplätze {spec.weapon_slots}   "
            f"Zubehörplätze {spec.accessory_slots}"
        )
        if spec is self._ship:
            return ShopRow(spec.name, "Ausgewählt", SELECTED_TEXT_COLOR, description)
        if self._progress.is_ship_unlocked(spec):
            return ShopRow(spec.name, "Freigeschaltet", OWNED_TEXT_COLOR, description)
        return ShopRow(spec.name, f"{spec.price} Münzen", COIN_COLOR, description)

    def _accessory_row(self, spec: AccessorySpec) -> ShopRow:
        if not self._progress.owns_accessory(spec):
            return ShopRow(spec.name, f"{spec.price} Münzen", COIN_COLOR, spec.description)
        if self._progress.is_equipped(self._ship, spec):
            return ShopRow(spec.name, "Ausgerüstet", SELECTED_TEXT_COLOR, spec.description)
        return ShopRow(spec.name, "Gekauft", OWNED_TEXT_COLOR, spec.description)

    def _default_tint_row(self) -> ShopRow:
        description = f"Standardfarbe von {self._ship.name}"
        if self._progress.active_tint(self._ship) is None:
            return ShopRow("Standard", "Aktiv", SELECTED_TEXT_COLOR, description)
        return ShopRow("Standard", "Kostenlos", OWNED_TEXT_COLOR, description)

    def _tint_row(self, spec: TintSpec) -> ShopRow:
        description = "Einmal kaufen, auf jedem Schiff einstellbar"
        if not self._progress.owns_tint(spec):
            return ShopRow(spec.name, f"{spec.price} Münzen", COIN_COLOR, description)
        if self._progress.active_tint(self._ship) is spec:
            return ShopRow(spec.name, "Aktiv", SELECTED_TEXT_COLOR, description)
        return ShopRow(spec.name, "Gekauft", OWNED_TEXT_COLOR, description)

    # --- Zeichnen ----------------------------------------------------------------

    def draw(self) -> None:
        screen = self.context.screen
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        menu_font = vp.font(MENU_FONT_SIZE)
        tab_font = vp.font(SHOP_TAB_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = menu_font.render("Shop", True, TEXT_COLOR)
        screen.blit(title, title.get_rect(center=(vp.center_x, vp.py(_TITLE_Y))))

        for index, (tab, x) in enumerate(zip(TABS, _TAB_XS, strict=True)):
            selected = index == self.tab_index
            text = tab_font.render(tab.value, True, SELECTED_TEXT_COLOR if selected else TEXT_COLOR)
            rect = text.get_rect(center=(vp.px(x), vp.py(_TAB_Y)))
            screen.blit(text, rect)
            if selected:
                underline_y = rect.bottom + vp.s(4)
                pygame.draw.line(
                    screen,
                    SELECTED_TEXT_COLOR,
                    (rect.left, underline_y),
                    (rect.right, underline_y),
                    max(1, vp.s(2)),
                )

        rows = self.rows()
        for index, row in enumerate(rows):
            y = vp.py(_ROW_TOP + index * _ROW_STEP)
            selected = index == self.row_index
            label = hint_font.render(
                row.label, True, SELECTED_TEXT_COLOR if selected else TEXT_COLOR
            )
            screen.blit(label, label.get_rect(midleft=(vp.px(_ROW_LEFT_X), y)))
            status = hint_font.render(row.status, True, row.status_color)
            screen.blit(status, status.get_rect(midright=(vp.px(_ROW_RIGHT_X), y)))
            if selected:
                marker = hint_font.render(">", True, SELECTED_TEXT_COLOR)
                screen.blit(marker, marker.get_rect(midright=(vp.px(_MARKER_X), y)))

        self._draw_preview()

        description = hint_font.render(rows[self.row_index].description, True, MUTED_TEXT_COLOR)
        screen.blit(description, description.get_rect(center=(vp.center_x, vp.py(_DESCRIPTION_Y))))

        if self._feedback_ttl > 0:
            feedback = hint_font.render(self._feedback, True, SELECTED_TEXT_COLOR)
            screen.blit(feedback, feedback.get_rect(center=(vp.center_x, vp.py(_FEEDBACK_Y))))

        hints = (
            "Links/Rechts: Reiter   Hoch/Runter: wählen",
            "Enter: kaufen / ausrüsten   Escape: zurück",
        )
        for hint_text, y in zip(hints, _HINT_YS, strict=True):
            hint = hint_font.render(hint_text, True, TEXT_COLOR)
            screen.blit(hint, hint.get_rect(center=(vp.center_x, vp.py(y))))

        draw_wallet(self.context)
        pygame.display.flip()

    def _preview_target(self) -> tuple[ShipSpec, Color | None]:
        """Welches Schiff in welcher Farbe rechts gezeigt wird — folgt dem Cursor."""
        if self.tab is ShopTab.SHIPS:
            spec = SHIPS[self.row_index]
            return spec, self._progress.ship_tint(spec)
        if self.tab is ShopTab.TINTS and self.row_index > 0:
            return self._ship, TINTS[self.row_index - 1].color
        if self.tab is ShopTab.TINTS:
            return self._ship, self._ship.tint
        return self._ship, self._progress.ship_tint(self._ship)

    def _draw_preview(self) -> None:
        screen = self.context.screen
        vp = self.context.viewport
        hint_font = vp.font(HINT_FONT_SIZE)
        spec, tint = self._preview_target()
        size = (vp.s(SHIP_PREVIEW_SIZE[0]), vp.s(SHIP_PREVIEW_SIZE[1]))
        preview = self.context.assets.load_ship(spec.sprite, size, tint)
        if not self._progress.is_ship_unlocked(spec):
            preview = dimmed(preview)
        center = vp.point(*_PREVIEW_CENTER)
        screen.blit(preview, preview.get_rect(center=center))

        name = hint_font.render(spec.name, True, TEXT_COLOR)
        screen.blit(name, name.get_rect(center=(center[0], vp.py(_PREVIEW_NAME_Y))))
        used = len(self._progress.equipped_accessories(spec))
        slots = hint_font.render(f"Zubehör {used}/{spec.accessory_slots}", True, MUTED_TEXT_COLOR)
        screen.blit(slots, slots.get_rect(center=(center[0], vp.py(_PREVIEW_SLOTS_Y))))


def _failure_text(result: ShopResult, name: str, price: int, ship: ShipSpec) -> str:
    if result is ShopResult.TOO_EXPENSIVE:
        return f"Nicht genug Münzen: {name} kostet {price}"
    if result is ShopResult.NO_FREE_SLOT:
        return f"{ship.name} hat keinen freien Zubehörplatz"
    if result is ShopResult.NOT_OWNED:
        return f"{name} zuerst kaufen"
    if result is ShopResult.ALREADY_OWNED:
        return f"{name} bereits gekauft"
    return ""
