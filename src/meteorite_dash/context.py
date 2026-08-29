from dataclasses import dataclass, field

import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import MIN_WINDOW_SIZE, REFERENCE_SIZE
from meteorite_dash.ships import SHIPS, ShipSpec
from meteorite_dash.starfield import StarField
from meteorite_dash.viewport import Viewport


@dataclass
class GameState:
    selected_ship_index: int = 0
    final_light_years: float = 0.0
    final_coins: int = 0
    # Session-Summe über alle Läufe — Haken für Währung/Persistenz (Issue #14).
    total_coins: int = 0

    @property
    def selected_ship(self) -> ShipSpec:
        return SHIPS[self.selected_ship_index]


@dataclass
class GameContext:
    screen: pygame.Surface
    clock: pygame.time.Clock
    menu_font: pygame.font.Font
    hint_font: pygame.font.Font
    music: MusicPlayer
    assets: AssetLoader
    state: GameState
    starfield: StarField
    viewport: Viewport = field(
        default_factory=lambda: Viewport(REFERENCE_SIZE[0], REFERENCE_SIZE[1])
    )
    _is_fullscreen: bool = field(default=False, init=False)
    _windowed_size: tuple[int, int] = field(default=REFERENCE_SIZE, init=False)

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    def apply_resize(self, size: tuple[int, int]) -> None:
        if self._is_fullscreen:
            return
        self._set_windowed(size)

    def toggle_fullscreen(self) -> None:
        if self._is_fullscreen:
            self._is_fullscreen = False
            self._set_windowed(self._windowed_size)
        else:
            self._windowed_size = self.screen.get_size()
            desktop = pygame.display.get_desktop_sizes()[0]
            self._set_screen(desktop, pygame.FULLSCREEN)
            self._is_fullscreen = True

    def _set_windowed(self, size: tuple[int, int]) -> None:
        width = max(size[0], MIN_WINDOW_SIZE[0])
        height = max(size[1], MIN_WINDOW_SIZE[1])
        self._set_screen((width, height), pygame.RESIZABLE)

    def _set_screen(self, size: tuple[int, int], flags: int) -> None:
        self.screen = pygame.display.set_mode(size, flags)
        width, height = self.screen.get_size()
        self.viewport.resize(width, height)
        self.starfield.resize(width, height)
