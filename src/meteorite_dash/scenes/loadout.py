"""Ausrüstungs-Szene vor dem Lauf: Vorrat auf die Zubehörplätze des Schiffs legen.

Zubehör ist Verbrauchsware (`accessories.py`): gekauft wird im Shop auf Vorrat,
hier wird entschieden, was in diesen Lauf mitgeht. Abgebucht wird erst beim
Start durch `GameScene` — wer mit Escape zurückgeht, verliert nichts.

Die Auswahl lebt in `Progress.equipped` und bleibt bestehen, solange der Vorrat
reicht: der nächste Lauf startet dann mit Enter durch.
"""

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
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.progress import Progress, ShopResult
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.widgets import draw_wallet
from meteorite_dash.ships import ShipSpec

# Layout im Referenzraum 800x600.
_TITLE_Y = 70
_SHIP_Y = 108
_ROW_TOP = 190
_ROW_STEP = 46
_ROW_LEFT_X = 110
_ROW_RIGHT_X = 520
_MARKER_X = 90
_PREVIEW_CENTER = (680, 230)
_PREVIEW_SLOTS_Y = 300
_DESCRIPTION_Y = 420
_FEEDBACK_Y = 452
_HINT_YS = (500, 530, 560)


class LoadoutScene(Scene):
    """Zubehör-Auswahl zwischen Hauptmenü und Lauf.

    `start` ist der Lauf, der nach Enter beginnt (`START_GAME` oder
    `START_DAILY`). Die Szene ändert nur die Platzbelegung; der Vorrat sinkt
    erst, wenn der Lauf tatsächlich losgeht.
    """

    def __init__(self, context: GameContext, *, start: Transition) -> None:
        super().__init__(context)
        self.start = start
        self.row_index = 0
        self._feedback = ""
        self._feedback_ttl = 0.0

    @property
    def _progress(self) -> Progress:
        """Persistenter Fortschritt aus dem `GameState`."""
        return self.context.state.progress

    @property
    def _ship(self) -> ShipSpec:
        """Schiff, das in den Lauf geht — es bestimmt die Zahl der Plätze."""
        return self.context.state.selected_ship

    # --- Eingabe ---------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        """Hoch/Runter wählt, Leertaste rüstet aus, Enter startet, Escape geht zurück."""
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_UP:
            self.row_index = (self.row_index - 1) % len(ACCESSORIES)
        elif event.key == pygame.K_DOWN:
            self.row_index = (self.row_index + 1) % len(ACCESSORIES)
        elif event.key == pygame.K_SPACE:
            self._toggle(ACCESSORIES[self.row_index])
        elif event.key == pygame.K_RETURN:
            self.finish(self.start)
        elif event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)

    def _toggle(self, spec: AccessorySpec) -> None:
        """Legt `spec` auf einen Platz des Schiffs bzw. nimmt es wieder herunter."""
        ship = self._ship
        result = self._progress.toggle_accessory(ship, spec)
        if result is ShopResult.OK:
            if self._progress.is_equipped(ship, spec):
                self._show(f"{spec.name} eingesetzt")
            else:
                self._show(f"{spec.name} abgelegt")
            self.context.save_progress()
        elif result is ShopResult.NOT_OWNED:
            self._show(f"{spec.name} ist alle — im Shop nachkaufen")
        elif result is ShopResult.NO_FREE_SLOT:
            self._show(f"{ship.name} hat nur {ship.accessory_slots} Zubehörplätze")

    def update(self, dt: float) -> None:
        """Lässt den Hinweis-Text ablaufen (Wandzeit, reine Deko)."""
        self._feedback_ttl = max(0.0, self._feedback_ttl - dt)

    def _show(self, message: str) -> None:
        """Zeigt einen Hinweis für `SHOP_FEEDBACK_SECONDS`."""
        self._feedback = message
        self._feedback_ttl = SHOP_FEEDBACK_SECONDS

    # --- Zeilen ----------------------------------------------------------------

    def rows(self) -> list[tuple[AccessorySpec, str, tuple[int, int, int]]]:
        """Je Zubehör: Katalog-Eintrag, Statustext und dessen Farbe."""
        ship = self._ship
        rows = []
        for spec in ACCESSORIES:
            count = self._progress.accessory_count(spec)
            if self._progress.is_equipped(ship, spec):
                slot = self._progress.equipped.get(ship.name, []).index(spec.id) + 1
                rows.append((spec, f"Platz {slot}   x{count}", SELECTED_TEXT_COLOR))
            elif count > 0:
                rows.append((spec, f"x{count}", OWNED_TEXT_COLOR))
            else:
                rows.append((spec, f"leer   {spec.price} Münzen", COIN_COLOR))
        return rows

    # --- Zeichnen ----------------------------------------------------------------

    def draw(self) -> None:
        """Zeichnet Titel, Schiff mit Platzbelegung, Zubehörliste, Hinweise und Wallet."""
        screen = self.context.screen
        vp = self.context.viewport
        ship = self._ship
        screen.fill(BACKGROUND_COLOR)
        menu_font = vp.font(MENU_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = menu_font.render("Ausrüstung", True, TEXT_COLOR)
        screen.blit(title, title.get_rect(center=(vp.center_x, vp.py(_TITLE_Y))))
        used = len(self._progress.equipped_accessories(ship))
        subtitle = hint_font.render(
            f"{ship.name} — Plätze {used}/{ship.accessory_slots}", True, MUTED_TEXT_COLOR
        )
        screen.blit(subtitle, subtitle.get_rect(center=(vp.center_x, vp.py(_SHIP_Y))))

        rows = self.rows()
        for index, (spec, status, status_color) in enumerate(rows):
            y = vp.py(_ROW_TOP + index * _ROW_STEP)
            selected = index == self.row_index
            label = hint_font.render(
                spec.name, True, SELECTED_TEXT_COLOR if selected else TEXT_COLOR
            )
            screen.blit(label, label.get_rect(midleft=(vp.px(_ROW_LEFT_X), y)))
            status_text = hint_font.render(status, True, status_color)
            screen.blit(status_text, status_text.get_rect(midright=(vp.px(_ROW_RIGHT_X), y)))
            if selected:
                marker = hint_font.render(">", True, SELECTED_TEXT_COLOR)
                screen.blit(marker, marker.get_rect(midright=(vp.px(_MARKER_X), y)))

        self._draw_preview()

        description = hint_font.render(rows[self.row_index][0].description, True, MUTED_TEXT_COLOR)
        screen.blit(description, description.get_rect(center=(vp.center_x, vp.py(_DESCRIPTION_Y))))

        if self._feedback_ttl > 0:
            feedback = hint_font.render(self._feedback, True, SELECTED_TEXT_COLOR)
            screen.blit(feedback, feedback.get_rect(center=(vp.center_x, vp.py(_FEEDBACK_Y))))

        hints = (
            "Zubehör hält einen Lauf — Nachschub gibt es im Shop",
            "Hoch/Runter: wählen   Leertaste: einsetzen",
            "Enter: starten   Escape: zurück",
        )
        for hint_text, y in zip(hints, _HINT_YS, strict=True):
            hint = hint_font.render(hint_text, True, TEXT_COLOR)
            screen.blit(hint, hint.get_rect(center=(vp.center_x, vp.py(y))))

        draw_wallet(self.context)
        pygame.display.flip()

    def _draw_preview(self) -> None:
        """Schiffsvorschau rechts in seiner gewählten Farbe, darunter die Platzbelegung."""
        screen = self.context.screen
        vp = self.context.viewport
        hint_font = vp.font(HINT_FONT_SIZE)
        ship = self._ship
        size = (vp.s(SHIP_PREVIEW_SIZE[0]), vp.s(SHIP_PREVIEW_SIZE[1]))
        preview = self.context.assets.load_ship(ship.sprite, size, self._progress.ship_tint(ship))
        center = vp.point(*_PREVIEW_CENTER)
        screen.blit(preview, preview.get_rect(center=center))

        equipped = self._progress.equipped_accessories(ship)
        text = ", ".join(spec.name for spec in equipped) if equipped else "ohne Zubehör"
        line = hint_font.render(text, True, MUTED_TEXT_COLOR)
        screen.blit(line, line.get_rect(center=(center[0], vp.py(_PREVIEW_SLOTS_Y))))
