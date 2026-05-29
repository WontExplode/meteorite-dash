import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from collections.abc import Iterator

import pygame
import pytest

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import HINT_FONT_SIZE, MENU_FONT_NAME, MENU_FONT_SIZE, WINDOW_SIZE
from meteorite_dash.context import GameContext, GameState


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
    )
    yield ctx
    pygame.quit()
