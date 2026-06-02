from typing import Literal

WindowSize = tuple[int, int]
Color = tuple[int, int, int]
MenuAction = Literal["start", "ship", "quit"]

WINDOW_SIZE: WindowSize = (800, 600)
# Design reference: every scale factor is relative to this. At this size all
# factors are exactly 1.0, so layout/gameplay are byte-identical to the original.
REFERENCE_SIZE: WindowSize = WINDOW_SIZE
# Smallest window we allow; guards against degenerate sizes / division by zero.
MIN_WINDOW_SIZE: WindowSize = (320, 240)
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
DEATH_SOUND = "gameovermusic.mp3"
GAME_MUSIC_TRACKS: tuple[str, ...] = (
    "gamemusic1.mp3",
    "gamemusic2.mp3",
    "gamemusic3.mp3",
)

PLAYER_SPEED = 300
PLAYER_SIZE: WindowSize = (64, 64)
PLAYER_START_POSITION: WindowSize = (50, 100)
SHIP_PREVIEW_SIZE: WindowSize = (96, 96)

# --- Hindernisse & Gegner ---
METEORITE_COLOR: Color = (120, 120, 130)
WAVE_ENEMY_COLOR: Color = (220, 90, 90)
HUNTER_ENEMY_COLOR: Color = (90, 200, 130)

METEORITE_RADIUS = 22
ENEMY_SIZE: WindowSize = (44, 44)

METEORITE_SPEED = 220.0
WAVE_ENEMY_SPEED = 180.0
HUNTER_ENEMY_SPEED = 160.0

WAVE_AMPLITUDE = 80.0
WAVE_FREQUENCY = 0.6
HUNTER_VERTICAL_SPEED = 140.0

SPAWN_INTERVAL_RANGE: tuple[float, float] = (0.6, 1.4)
METEORITE_WEIGHT = 3.0
WAVE_ENEMY_WEIGHT = 1.5
HUNTER_ENEMY_WEIGHT = 1.0
