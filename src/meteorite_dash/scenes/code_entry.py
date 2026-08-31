"""Code eingeben: drei Wörter tippen, Lauf vom Relay holen, antreten oder ansehen."""

import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    CODE_ENTRY_ACTIONS_TOP,
    CODE_ENTRY_BOX_RECT,
    CODE_ENTRY_CURSOR_BLINK_MS,
    CODE_ENTRY_FOOTER_TOP,
    CODE_ENTRY_HINT_TOP,
    CODE_ENTRY_MAX_CHARS,
    CODE_ENTRY_MESSAGE_TOP,
    CODE_ENTRY_RESULT_TOP,
    CODE_ENTRY_TITLE_TOP,
    COMMUNITY_STATUS_COLOR,
    HINT_FONT_SIZE,
    MENU_FONT_SIZE,
    MUTED_TEXT_COLOR,
    SCORE_FONT_SIZE,
    SELECTED_TEXT_COLOR,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.exchange import LOOKUP_SEARCHING, describe_run, share_name
from meteorite_dash.phrase import matches, normalize
from meteorite_dash.replay import Replay
from meteorite_dash.scenes.base import Scene, Transition

_ALLOWED_CHARS = frozenset("abcdefghijklmnopqrstuvwxyz -")
HINT_FORMAT = "DREI WÖRTER AUS DER LISTE, Z. B. apfel berg wolke"
OFFLINE_LOCAL_ONLY = "OFFLINE — NUR SCHON GEHOLTE CODES"


class CodeEntryScene(Scene):
    """Tastatur -> Phrase -> `RunExchange.start_lookup` (Thread) -> Ergebnis per
    `update`. Ohne Exchange (offline) zählt nur, was schon im `ReplayStore` liegt."""

    captures_text = True  # `f` ist hier ein Buchstabe, kein Vollbild-Shortcut

    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        self.text = ""
        self.message = ""
        self.result: Replay | None = None
        self._phrase: str | None = None  # gerade laufende Suche
        self._waiting = False

    # --- Eingabe -------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)
        elif event.key == pygame.K_RETURN:
            self.confirm()
        elif event.key == pygame.K_TAB:
            if self.result is not None:
                self.context.state.pending_replay = self.result
                self.finish(Transition.SPECTATE)
        elif event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            self.result = None
        else:
            self.type_text(getattr(event, "unicode", ""))

    def type_text(self, chars: str) -> None:
        for char in chars.lower().replace("ß", "ss"):
            if char in _ALLOWED_CHARS and len(self.text) < CODE_ENTRY_MAX_CHARS:
                self.text += char
                self.result = None

    def confirm(self) -> None:
        if self.result is not None:
            self.context.state.pending_replay = self.result
            # Vor dem Rennen wird ausgerüstet — es kostet Zubehör wie jeder Lauf.
            self.finish(Transition.LOADOUT_RACE)
            return
        if self._waiting:
            return
        phrase = normalize(self.text)
        if phrase is None:
            self.message = HINT_FORMAT
            return
        self.text = phrase
        self.lookup(phrase)

    def lookup(self, phrase: str) -> None:
        exchange = self.context.exchange
        if exchange is None:
            store = self.context.replays
            local = store.load(share_name(phrase)) if store is not None else None
            if local is not None and matches(phrase, local.state_hash):
                self.found(local)
            else:
                self.message = OFFLINE_LOCAL_ONLY
            return
        self._phrase = phrase
        self._waiting = True
        self.message = LOOKUP_SEARCHING
        exchange.start_lookup(phrase)

    def found(self, replay: Replay) -> None:
        self.result = replay
        self.message = describe_run(replay)

    def update(self, dt: float) -> None:
        if not self._waiting or self.context.exchange is None:
            return
        lookup = self.context.exchange.lookup
        if lookup is None or not lookup.done or lookup.phrase != self._phrase:
            return
        self._waiting = False
        if lookup.replay is not None:
            self.found(lookup.replay)
        else:
            self.message = lookup.message

    # --- Zeichnen ------------------------------------------------------------------

    def draw(self) -> None:
        screen = self.context.screen
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x
        title_font = vp.font(MENU_FONT_SIZE)
        text_font = vp.font(SCORE_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = title_font.render("CODE EINGEBEN", True, TEXT_COLOR)
        screen.blit(title, title.get_rect(center=(center_x, vp.py(CODE_ENTRY_TITLE_TOP))))
        hint = hint_font.render(HINT_FORMAT, True, MUTED_TEXT_COLOR)
        screen.blit(hint, hint.get_rect(center=(center_x, vp.py(CODE_ENTRY_HINT_TOP))))

        x, y, w, h = CODE_ENTRY_BOX_RECT
        box = pygame.Rect(vp.px(x), vp.py(y), vp.px(x + w) - vp.px(x), vp.py(y + h) - vp.py(y))
        pygame.draw.rect(screen, MUTED_TEXT_COLOR, box, max(1, vp.s(2)))
        cursor_on = (pygame.time.get_ticks() // CODE_ENTRY_CURSOR_BLINK_MS) % 2 == 0
        shown = self.text + ("_" if cursor_on and self.result is None else "")
        entry = text_font.render(shown or " ", True, SELECTED_TEXT_COLOR)
        screen.blit(entry, entry.get_rect(midleft=(box.left + vp.s(16), box.centery)))

        if self.message:
            color = COMMUNITY_STATUS_COLOR if self.result is not None else TEXT_COLOR
            message = hint_font.render(self.message, True, color)
            screen.blit(message, message.get_rect(center=(center_x, vp.py(CODE_ENTRY_MESSAGE_TOP))))

        if self.result is not None:
            found = text_font.render("LAUF GEFUNDEN", True, SELECTED_TEXT_COLOR)
            screen.blit(found, found.get_rect(center=(center_x, vp.py(CODE_ENTRY_RESULT_TOP))))
            actions = hint_font.render("ENTER: ANTRETEN   TAB: ANSEHEN", True, TEXT_COLOR)
            screen.blit(actions, actions.get_rect(center=(center_x, vp.py(CODE_ENTRY_ACTIONS_TOP))))

        footer = hint_font.render("ENTER: SUCHEN   ESC: ZURÜCK", True, TEXT_COLOR)
        screen.blit(footer, footer.get_rect(center=(center_x, vp.py(CODE_ENTRY_FOOTER_TOP))))
        pygame.display.flip()
