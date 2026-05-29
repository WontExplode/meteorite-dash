from dataclasses import dataclass

import pygame

from meteorite_dash.assets import SHIP_IMAGES, AssetLoader
from meteorite_dash.audio import MusicPlayer


@dataclass
class GameState:
    selected_ship_index: int = 0

    @property
    def selected_ship_filename(self) -> str:
        return SHIP_IMAGES[self.selected_ship_index]


@dataclass
class GameContext:
    screen: pygame.Surface
    clock: pygame.time.Clock
    menu_font: pygame.font.Font
    hint_font: pygame.font.Font
    music: MusicPlayer
    assets: AssetLoader
    state: GameState
