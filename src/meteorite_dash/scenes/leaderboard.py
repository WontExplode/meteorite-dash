"""Daily-Bestenliste: Top-Läufe zum Tages-Seed, eigener Rang, Neu-Laden von den Relays."""

import pygame

from meteorite_dash.config import (
    BACKGROUND_COLOR,
    COMMUNITY_STATUS_COLOR,
    DEATH_MODE_COLOR,
    HINT_FONT_SIZE,
    LEADERBOARD_COLUMNS,
    LEADERBOARD_HEADER_TOP,
    LEADERBOARD_HINT_TOP,
    LEADERBOARD_OWN_TOP,
    LEADERBOARD_ROW_SPACING,
    LEADERBOARD_ROWS_TOP,
    LEADERBOARD_SIZE,
    LEADERBOARD_STATUS_TOP,
    LEADERBOARD_SUBTITLE_TOP,
    LEADERBOARD_TITLE_TOP,
    MENU_FONT_SIZE,
    MUTED_TEXT_COLOR,
    SCORE_FONT_SIZE,
    SELECTED_TEXT_COLOR,
    TEXT_COLOR,
)
from meteorite_dash.context import GameContext
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.leaderboard import Leaderboard, LeaderboardEntry, build_leaderboard
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.score import format_light_years


class LeaderboardScene(Scene):
    """Liest nur den `ReplayStore`; das Netz läuft im `RunExchange` nebenher und
    die Liste baut sich neu, sobald sich dessen Status ändert."""

    def __init__(self, context: GameContext, *, seed: int | None = None, label: str = "") -> None:
        super().__init__(context)
        if seed is None:
            day = today_utc()
            seed, label = daily_seed(day), day.isoformat()
        self.seed = seed
        self.label = label
        self.board: Leaderboard = self._build()
        self._seen_status = self._status()

    def _status(self) -> str:
        exchange = self.context.exchange
        return exchange.status if exchange is not None else ""

    def _build(self) -> Leaderboard:
        store = self.context.replays
        replays = store.all() if store is not None else []
        return build_leaderboard(replays, self.seed)

    def refresh(self) -> None:
        """Neu von den Relays holen (Hintergrund); die Liste folgt über `update`."""
        if self.context.exchange is not None:
            self.context.exchange.prefetch(self.seed)
        self.board = self._build()

    def on_enter(self) -> None:
        self.refresh()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_SPACE):
            self.finish(Transition.MAIN_MENU)
        elif event.key == pygame.K_r:
            self.refresh()

    def update(self, dt: float) -> None:
        status = self._status()
        if status != self._seen_status:
            self._seen_status = status
            self.board = self._build()

    def draw(self) -> None:
        screen = self.context.screen
        vp = self.context.viewport
        screen.fill(BACKGROUND_COLOR)
        center_x = vp.center_x
        title_font = vp.font(MENU_FONT_SIZE)
        row_font = vp.font(SCORE_FONT_SIZE)
        hint_font = vp.font(HINT_FONT_SIZE)

        title = title_font.render("DAILY BESTENLISTE", True, TEXT_COLOR)
        screen.blit(title, title.get_rect(center=(center_x, vp.py(LEADERBOARD_TITLE_TOP))))
        subtitle = hint_font.render(f"{self.label}   SEED {self.seed}", True, DEATH_MODE_COLOR)
        screen.blit(subtitle, subtitle.get_rect(center=(center_x, vp.py(LEADERBOARD_SUBTITLE_TOP))))
        status = self._status()
        if status:
            status_text = hint_font.render(status, True, COMMUNITY_STATUS_COLOR)
            screen.blit(
                status_text, status_text.get_rect(center=(center_x, vp.py(LEADERBOARD_STATUS_TOP)))
            )

        rank_x, name_x, ly_x, ship_x = LEADERBOARD_COLUMNS
        header_y = vp.py(LEADERBOARD_HEADER_TOP)
        for x, label in (
            (rank_x, "#"),
            (name_x, "SPIELER"),
            (ly_x, "LICHTJAHRE"),
            (ship_x, "SCHIFF"),
        ):
            header = hint_font.render(label, True, MUTED_TEXT_COLOR)
            screen.blit(header, header.get_rect(topleft=(vp.px(x), header_y)))

        top = self.board.top(LEADERBOARD_SIZE)
        if not top:
            empty = row_font.render("NOCH KEINE LÄUFE ZU DIESEM SEED", True, MUTED_TEXT_COLOR)
            screen.blit(empty, empty.get_rect(center=(center_x, vp.py(LEADERBOARD_ROWS_TOP))))
        for index, entry in enumerate(top):
            self._draw_row(
                row_font, entry, vp.py(LEADERBOARD_ROWS_TOP + index * LEADERBOARD_ROW_SPACING)
            )

        own_line = self._own_line()
        own_text = row_font.render(own_line, True, SELECTED_TEXT_COLOR)
        screen.blit(own_text, own_text.get_rect(center=(center_x, vp.py(LEADERBOARD_OWN_TOP))))

        hint = hint_font.render("R: AKTUALISIEREN   ESC: ZURÜCK", True, TEXT_COLOR)
        screen.blit(hint, hint.get_rect(center=(center_x, vp.py(LEADERBOARD_HINT_TOP))))
        pygame.display.flip()

    def _draw_row(self, font: pygame.font.Font, entry: LeaderboardEntry, y: int) -> None:
        vp = self.context.viewport
        color = SELECTED_TEXT_COLOR if entry.is_own else TEXT_COLOR
        rank_x, name_x, ly_x, ship_x = LEADERBOARD_COLUMNS
        cells = (
            (rank_x, f"{entry.rank}."),
            (name_x, entry.name),
            (ly_x, format_light_years(entry.light_years)),
            (ship_x, entry.ship),
        )
        for x, text in cells:
            surface = font.render(text, True, color)
            self.context.screen.blit(surface, surface.get_rect(topleft=(vp.px(x), y)))

    def _own_line(self) -> str:
        own = self.board.own
        if own is None:
            return "DU: NOCH KEIN LAUF ZU DIESEM SEED"
        return (
            f"DU: PLATZ {own.rank} VON {len(self.board)}   "
            f"{format_light_years(own.light_years)} LICHTJAHRE"
        )
