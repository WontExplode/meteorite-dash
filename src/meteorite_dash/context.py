from dataclasses import dataclass, field

import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import MIN_WINDOW_SIZE, REFERENCE_SIZE
from meteorite_dash.exchange import RunExchange
from meteorite_dash.persistence import SaveStore
from meteorite_dash.progress import Progress
from meteorite_dash.replay import Replay, ReplayStore, RunMode
from meteorite_dash.ships import SHIPS, ShipSpec
from meteorite_dash.starfield import StarField
from meteorite_dash.viewport import Viewport


@dataclass
class GameState:
    selected_ship_index: int = 0
    final_light_years: float = 0.0
    final_coins: int = 0
    final_seed: int = 0
    final_mode: RunMode = RunMode.FREE
    final_label: str = ""  # Daily: ISO-Datum
    # Bisheriger Rekord (Ghost) zum Seed des letzten Laufs; None = kein Vergleich.
    final_record_light_years: float | None = None
    # Pubkey des Rekordhalters, wenn der Ghost ein Community-Lauf war; sonst leer.
    final_record_author: str = ""
    # Zuschauer-Modus beendet: Autor des angesehenen Laufs ("" = eigener); None = gespielt.
    final_spectate_author: str | None = None
    # Per Code geholter Lauf, den die nächste Szene als Ghost (Rennen) oder Replay startet.
    pending_replay: Replay | None = None
    # Aufzeichnung des letzten beendeten Laufs (Issue #34), für Death-Screen/Ghost.
    last_replay: Replay | None = None
    # Persistenter Fortschritt: Münz-Guthaben, Freischaltungen, Ausrüstung (Issue #14).
    progress: Progress = field(default_factory=Progress)

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
    # Ohne Store (Tests) bleibt der Fortschritt im Speicher.
    store: SaveStore | None = None
    # Ohne ReplayStore (Tests) werden Läufe nicht auf Platte aufgezeichnet.
    replays: ReplayStore | None = None
    # Ohne Exchange (Tests, `METEORITE_DASH_OFFLINE`) wird nichts geteilt oder geholt.
    exchange: RunExchange | None = None
    _is_fullscreen: bool = field(default=False, init=False)
    _windowed_size: tuple[int, int] = field(default=REFERENCE_SIZE, init=False)

    @property
    def is_fullscreen(self) -> bool:
        return self._is_fullscreen

    def save_progress(self) -> None:
        if self.store is not None:
            self.store.save(self.state.progress)

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
