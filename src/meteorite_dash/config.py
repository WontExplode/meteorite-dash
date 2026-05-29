from typing import Literal

WindowSize = tuple[int, int]
Color = tuple[int, int, int]
MenuAction = Literal["start", "ship", "quit"]

WINDOW_SIZE: WindowSize = (800, 600)
CAPTION = "Meteorite Dash"
FPS = 60

BACKGROUND_COLOR: Color = (10, 10, 20)
TEXT_COLOR: Color = (220, 220, 230)
SELECTED_TEXT_COLOR: Color = (255, 210, 80)

MENU_FONT_NAME = "arial"
MENU_FONT_SIZE = 42
HINT_FONT_SIZE = 22

MENU_ITEMS: tuple[tuple[str, MenuAction], ...] = (
    ("Start", "start"),
    ("Raumschiff auswählen", "ship"),
    ("Beenden", "quit"),
)

MENU_MUSIC = "menumusic.mp3"
GAME_MUSIC_TRACKS: tuple[str, ...] = (
    "gamemusic1.mp3",
    "gamemusic2.mp3",
    "gamemusic3.mp3",
)

PLAYER_SPEED = 300
PLAYER_SIZE: WindowSize = (64, 64)
PLAYER_START_POSITION: WindowSize = (50, 100)
SHIP_PREVIEW_SIZE: WindowSize = (96, 96)
