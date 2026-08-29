"""Kleine Zeichen-Helfer, die mehrere Menü-Szenen teilen."""

import pygame

from meteorite_dash.config import (
    COIN_COLOR,
    LOCKED_PREVIEW_ALPHA,
    SCORE_FONT_SIZE,
    WALLET_TOP_RIGHT,
)
from meteorite_dash.context import GameContext
from meteorite_dash.score import format_coins


def draw_wallet(context: GameContext) -> None:
    """Münz-Guthaben oben rechts — dieselbe Ecke wie der Score im Spiel."""
    vp = context.viewport
    text = vp.font(SCORE_FONT_SIZE).render(
        f"MÜNZEN {format_coins(context.state.progress.coins)}", True, COIN_COLOR
    )
    context.screen.blit(text, text.get_rect(topright=vp.point(*WALLET_TOP_RIGHT)))


def dimmed(surface: pygame.Surface) -> pygame.Surface:
    """Abgedunkelte Kopie für gesperrte Vorschauen; das Original (Cache) bleibt unberührt."""
    copy = surface.copy()
    copy.set_alpha(LOCKED_PREVIEW_ALPHA)
    return copy
