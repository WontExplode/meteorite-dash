import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from collections.abc import Iterator

import pygame
import pytest

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import WINDOW_SIZE
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.starfield import StarField


@pytest.fixture
def context() -> Iterator[GameContext]:
    pygame.init()
    screen = pygame.display.set_mode(WINDOW_SIZE)
    ctx = GameContext(
        screen=screen,
        clock=pygame.time.Clock(),
        music=MusicPlayer(),
        assets=AssetLoader(),
        state=GameState(),
        starfield=StarField(screen.get_width(), screen.get_height()),
    )
    yield ctx
    pygame.quit()
