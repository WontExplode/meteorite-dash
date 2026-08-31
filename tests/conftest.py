"""Fixtures der Testsuite plus headless-Treiber, bevor `pygame` importiert wird.

Nur `tests/` braucht das: die Doctests aus `src/` (`--doctest-modules`) fassen
kein Display an, und keins der Spielmodule startet SDL beim Import — erst
`App.run` und `GameContext` rufen `pygame.init`/`set_mode`.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
# Kein Test darf ins Netz: `App()` baut ohne Exchange, Fake-Relays kommen explizit.
os.environ.setdefault("METEORITE_DASH_OFFLINE", "1")

from collections.abc import Iterator

import pygame
import pytest

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import HINT_FONT_SIZE, MENU_FONT_NAME, MENU_FONT_SIZE, WINDOW_SIZE
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.starfield import StarField


@pytest.fixture
def context() -> Iterator[GameContext]:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    ctx = GameContext(
        screen=screen,
        clock=pygame.time.Clock(),
        menu_font=pygame.font.SysFont(MENU_FONT_NAME, MENU_FONT_SIZE),
        hint_font=pygame.font.SysFont(MENU_FONT_NAME, HINT_FONT_SIZE),
        music=MusicPlayer(),
        assets=AssetLoader(),
        state=GameState(),
        starfield=StarField(screen.get_width(), screen.get_height()),
    )
    yield ctx
    pygame.quit()
