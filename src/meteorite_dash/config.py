from typing import Literal, NamedTuple

WindowSize = tuple[int, int]
Color = tuple[int, int, int]
MenuAction = Literal["start", "ship", "quit"]


class MeteoriteVariant(NamedTuple):
    radius: int
    images: tuple[str, str]
    hp: int
    contact_damage: int


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
STAT_BAR_COLOR: Color = (60, 60, 80)
DEATH_BORDER_COLOR: Color = (255, 80, 80)
DEATH_HIGHLIGHT_COLOR: Color = (255, 210, 80)
DEATH_MUTED_COLOR: Color = (120, 120, 150)

MENU_FONT_NAME = "arial"
MENU_FONT_SIZE = 42
HINT_FONT_SIZE = 22
DEATH_TITLE_FONT_SIZE = 84
DEATH_SUBTITLE_FONT_SIZE = 28
DEATH_MESSAGE_FONT_SIZE = 24

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

# Globaler Strömungswiderstand: bremst proportional zur Geschwindigkeit und
# bestimmt zusammen mit thrust/mass der Schiffe das Flugverhalten.
DRAG = 4.0
PLAYER_SIZE: WindowSize = (64, 64)
PLAYER_START_POSITION: WindowSize = (50, 100)
SHIP_PREVIEW_SIZE: WindowSize = (96, 96)
SHIP_SLOT_OFFSETS: tuple[int, int, int] = (-180, 0, 180)

# --- Hindernisse & Gegner ---
METEORITE_COLOR: Color = (120, 120, 130)
WAVE_ENEMY_COLOR: Color = (220, 90, 90)
HUNTER_ENEMY_COLOR: Color = (90, 200, 130)

METEORITE_VARIANTS: tuple[MeteoriteVariant, ...] = (
    MeteoriteVariant(20, ("AsteroidTiny.png", "AsteroidTiny2.png"), hp=10, contact_damage=15),
    MeteoriteVariant(30, ("AsteroidSmall.png", "AsteroidSmall2.png"), hp=20, contact_damage=22),
    MeteoriteVariant(42, ("AsteroidMedium.png", "AsteroidMedium2.png"), hp=40, contact_damage=30),
    MeteoriteVariant(60, ("AsteroidLarge.png", "AsteroidLarge2.png"), hp=70, contact_damage=45),
)
ENEMY_SIZE: WindowSize = (44, 44)
WAVE_ENEMY_HP = 20
HUNTER_ENEMY_HP = 30
WAVE_ENEMY_CONTACT_DAMAGE = 25
HUNTER_ENEMY_CONTACT_DAMAGE = 35

METEORITE_SPEED = 220.0
WAVE_ENEMY_SPEED = 180.0
HUNTER_ENEMY_SPEED = 160.0

WAVE_AMPLITUDE = 80.0
WAVE_FREQUENCY = 0.6
HUNTER_VERTICAL_SPEED = 140.0

SPAWN_INTERVAL_RANGE: tuple[float, float] = (0.6, 1.4)
METEORITE_WEIGHT = 8.0
WAVE_ENEMY_WEIGHT = 2.0
HUNTER_ENEMY_WEIGHT = 0.5

AMMO_PICKUP_WEIGHT = 1.5

# --- Waffen & Projektile ---
STANDARD_WEAPON_MAX_AMMO = 7
STANDARD_WEAPON_DAMAGE = 10
PROJECTILE_SPEED = 500.0
PROJECTILE_SIZE: WindowSize = (16, 8)
PROJECTILE_COLOR: Color = (255, 255, 120)
SHOOT_COOLDOWN = 0.25
STANDARD_WEAPON_SOUND = "standard-gun.mp3"

AMMO_PICKUP_SIZE: WindowSize = (24, 24)
AMMO_PICKUP_COLOR: Color = (255, 210, 80)
AMMO_PICKUP_SPEED = 180.0
AMMO_PICKUP_HIGHLIGHT_COLOR = (255, 240, 180)

WEAPON_HUD_FONT_SIZE = 20
WEAPON_HUD_TOP_LEFT: WindowSize = (24, 24)
HP_HUD_TOP_LEFT: WindowSize = (24, 52)

# --- Score ---
SCORE_LIGHT_YEARS_PER_SECOND = 12.0
SCORE_FONT_SIZE = 24
SCORE_TOP_RIGHT: WindowSize = (776, 24)
SCORE_ALPHA = 175
