"""Zentrale Spielkonstanten — eine Quelle der Wahrheit für Werte, Größen und Gewichte.

Positionen und Größen der Spielwelt und des HUD sind Referenz-px (800x600);
der `Viewport` rechnet sie beim Zeichnen ins Fenster um.
"""

from typing import Literal, NamedTuple

WindowSize = tuple[int, int]
Color = tuple[int, int, int]
MenuAction = Literal["start", "daily", "leaderboard", "code", "ship", "shop", "quit"]


class MeteoriteVariant(NamedTuple):
    """Meteoriten-Größe: Radius, zwei Bildvarianten, HP und Kollisionsschaden."""

    radius: int
    images: tuple[str, str]
    hp: int
    contact_damage: int


class CoinPatternSpec(NamedTuple):
    """Ein Münz-Muster: Name (Layout in `coins.py`), Spawn-Gewicht, Bonus bei Komplettierung."""

    name: str
    weight: float
    bonus: int


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
MUTED_TEXT_COLOR: Color = (120, 120, 150)
OWNED_TEXT_COLOR: Color = (140, 255, 160)

MENU_FONT_NAME = "default"
MENU_FONT_SIZE = 42
HINT_FONT_SIZE = 22
DEATH_TITLE_FONT_SIZE = 84
DEATH_SUBTITLE_FONT_SIZE = 28
DEATH_MESSAGE_FONT_SIZE = 24

MENU_ITEMS: tuple[tuple[str, MenuAction], ...] = (
    ("Start", "start"),
    ("Daily Run", "daily"),
    ("Daily Bestenliste", "leaderboard"),
    ("Code eingeben", "code"),
    ("Raumschiff auswählen", "ship"),
    ("Shop", "shop"),
    ("Beenden", "quit"),
)

MENU_ITEM_FONT_SIZE = 36  # kleiner als der Titel, damit sieben Einträge ins Bild passen
# Referenz-y je Menüpunkt, gruppiert in Blöcke: Start | Daily/Community
# (mit Status-Zeile darunter) + Code eingeben | Raumschiff/Shop | Beenden.
MENU_ITEM_TOPS: tuple[int, ...] = (186, 240, 278, 316, 378, 416, 472)
MENU_SELECTED_SHIP_TOP = 508
MENU_HINT_TOP = 538

# --- Hauptmenü-Styling (Endgame-Look wie der Death-Screen) ---
MENU_TITLE_FONT_SIZE = 56
MENU_TITLE_TOP = 120
MENU_TITLE_SHADOW_COLOR: Color = (90, 55, 0)
MENU_BORDER_COLOR: Color = (90, 140, 200)
MENU_BORDER_INNER_COLOR: Color = (70, 70, 100)
MENU_SCANLINE_COLOR: Color = (18, 18, 32)
MENU_SCANLINE_GAP = 8
# Rahmen-Rechtecke in Referenz-px (x, y, Breite, Höhe).
MENU_BORDER_RECT: tuple[int, int, int, int] = (8, 8, 784, 584)
MENU_BORDER_INNER_RECT: tuple[int, int, int, int] = (18, 18, 764, 564)

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
# Unzerstörbare Meteoriten (Projektskizze): Panzergestein, das kein Schuss
# knackt — es muss umflogen werden. Silhouette und Sprites sind dieselben wie
# beim normalen Meteoriten; einziges Warnsignal ist die metallische Tönung,
# deshalb liegt sie weit weg von `METEORITE_COLOR`.
INDESTRUCTIBLE_METEORITE_COLOR: Color = (176, 196, 222)
# Helligkeitsstufen des Panzergesteins, vom unbeleuchteten Metall bis zur
# vollen Reflexion. Der `AssetLoader` entsättigt das Sprite zuerst und
# **addiert** dann diesen Wert (`BLEND_RGB_ADD`). Beides ist nötig: die
# Asteroiden-Sprites sind blaustichig, ein fester Summand ließe je nach Pixel
# einen Farbstich stehen (die Blauwerte streuen von 27 bis 80) — und sie liegen
# bei rund (32, 40, 64), also fast schwarz, weshalb Multiplizieren sie nur
# weiter abdunkeln könnte. Entsättigt und aufgehellt ergibt Stufe 0 etwa Grau
# 95, die letzte etwa Grau 200. Feste Liste statt stetiger Kurve, damit der
# Bild-Cache beschränkt bleibt: eine Surface je Stufe und Größe statt einer je
# Frame.
INDESTRUCTIBLE_METEORITE_SHEEN: tuple[Color, ...] = (
    (50, 50, 50),
    (65, 65, 65),
    (80, 80, 80),
    (95, 95, 95),
    (110, 110, 110),
    (125, 125, 125),
    (140, 140, 140),
    (155, 155, 155),
)

# --- Lichtbänder ("Sonne") --------------------------------------------------
# Zwei schräge Streifen liegen über dem Referenzraum. Wo ein Panzerfels sie
# kreuzt, blitzt er auf — er reflektiert. Rein optisch: kein Sim-Zustand, keine
# Wirkung auf Kollision, Hash oder Replay. Nur die unzerstörbaren Meteoriten
# reagieren darauf; normales Gestein bleibt stumpf, damit der Unterschied das
# Warnsignal bleibt.
LIGHT_BAND_START_DEGREES = 60.0
# Abstand zweier Streifen, gemessen längs ihrer Normalen (Referenz-px). Quer zu
# den Streifen legt ein Meteorit rund 745 px zurück, bis er links hinausfliegt.
# 400 px Abstand ergeben beim Startwinkel auf jeder Flughöhe genau zwei
# Reflexionen pro Überflug. Über den ganzen Sonnenbogen bleiben es zwei bis
# drei — weiter auseinander, und bei flachem Winkel fällt eine ganz aus.
LIGHT_BAND_PERIOD = 400.0
# Streifenprofil, beide als Anteil von `LIGHT_BAND_PERIOD`. Bewusst
# unsymmetrisch: der Fels läuft in den Streifen hinein und blitzt auf kurzer
# Strecke auf (`EDGE`), danach klingt die Reflexion über eine längere Strecke
# ab (`FADE`) — so sieht man eine Reflexion mit Nachglühen und nicht ein
# gleichmäßig helles Band. Zusammen gut ein Sechstel des Streifenabstands,
# der Rest liegt im Schatten.
LIGHT_BAND_EDGE_WIDTH = 0.02
LIGHT_BAND_FADE_WIDTH = 0.14
# Die "Sonne" kippt die Streifen von `LIGHT_BAND_START_DEGREES` um
# `LIGHT_SUN_SWING_DEGREES` weiter und wieder zurück, eine volle Bewegung je
# `LIGHT_SUN_PERIOD_SECONDS`. Bewusst ein Pendel und keine volle Umdrehung:
# bei 180 Grad lägen die Streifen parallel zur Flugbahn, kein Meteorit würde
# je einen kreuzen und alle Reflexionen fielen aus. Der Bogen 60 bis 120 Grad
# hält den Winkel zur Flugbahn immer steil genug für zwei Reflexionen.
LIGHT_SUN_SWING_DEGREES = 60.0
LIGHT_SUN_PERIOD_SECONDS = 240.0
# Platzhalter: `take_damage` zieht nie ab, die HP sinken nie. Der Wert taucht
# nur im `state_key` auf und hält das `Damageable`-Protokoll erfüllt — sonst
# flögen Projektile wirkungslos hindurch, statt am Panzer zu zerschellen.
INDESTRUCTIBLE_METEORITE_HP = 1
INDESTRUCTIBLE_METEORITE_VARIANTS: tuple[MeteoriteVariant, ...] = (
    MeteoriteVariant(
        30,
        ("AsteroidSmall.png", "AsteroidSmall2.png"),
        hp=INDESTRUCTIBLE_METEORITE_HP,
        contact_damage=30,
    ),
    MeteoriteVariant(
        42,
        ("AsteroidMedium.png", "AsteroidMedium2.png"),
        hp=INDESTRUCTIBLE_METEORITE_HP,
        contact_damage=40,
    ),
    MeteoriteVariant(
        60,
        ("AsteroidLarge.png", "AsteroidLarge2.png"),
        hp=INDESTRUCTIBLE_METEORITE_HP,
        contact_damage=55,
    ),
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
# Selten: ein Hindernis, gegen das Munition nichts ausrichtet, soll überraschen,
# nicht die Bahn verstopfen.
INDESTRUCTIBLE_METEORITE_WEIGHT = 1.5
# Spawn-Würfe, die ein `accept`-Prädikat ablehnt, werden so oft wiederholt;
# danach fällt der Spawn aus.
SPAWN_MAX_ATTEMPTS = 5

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
DIFFICULTY_DEBUG_HUD_FONT_SIZE = 16
DIFFICULTY_DEBUG_HUD_TOP_LEFT: WindowSize = (24, 108)
DIFFICULTY_DEBUG_HUD_LINE_SPACING = 19
DIFFICULTY_DEBUG_HUD_COLOR: Color = (255, 210, 120)

# --- Score ---
SCORE_LIGHT_YEARS_PER_SECOND = 12.0
SCORE_FONT_SIZE = 24
SCORE_TOP_RIGHT: WindowSize = (776, 24)
SCORE_ALPHA = 175

# --- Münzen (Collectibles, Issue #14) ---
COIN_COLOR: Color = (255, 205, 60)
COIN_RIM_COLOR: Color = (190, 130, 20)
COIN_RADIUS = 12
COIN_SPEED = 220.0
COIN_VALUE = 1
# Abstände innerhalb eines Musters (Referenz-px): horizontal zwischen Münzen,
# vertikal zwischen Reihen bei mehrzeiligen Mustern (Raute).
COIN_SPACING = 40.0
COIN_ROW_SPACING = 48.0
COIN_WAVE_AMPLITUDE = 70.0
COIN_ARC_HEIGHT = 100.0
COIN_ZIGZAG_STEP = 30.0
# Dreh-Animation: Umdrehungen pro Sekunde und Phasenversatz je Münze im Muster.
COIN_SPIN_HZ = 1.5
COIN_SPIN_PHASE_STEP = 0.4
COIN_MIN_SPIN_WIDTH = 0.3  # Anteil des Durchmessers bei Kantenansicht
COIN_SPAWN_INTERVAL_RANGE: tuple[float, float] = (2.0, 4.5)
# Mindestabstand (Referenz-px) zwischen Münzen und Gefahren beim Spawn. Münzen
# und Meteoriten sind gleich schnell — eine Überlappung bliebe sonst dauerhaft.
COIN_HAZARD_CLEARANCE = 12
COIN_PATTERNS: tuple[CoinPatternSpec, ...] = (
    CoinPatternSpec("line", 4.0, 3),
    CoinPatternSpec("wave", 3.0, 5),
    CoinPatternSpec("arc", 3.0, 5),
    CoinPatternSpec("zigzag", 2.0, 6),
    CoinPatternSpec("diamond", 1.5, 8),
)
COINS_TOP_RIGHT: WindowSize = (776, 52)
COIN_BONUS_TOP_RIGHT: WindowSize = (776, 80)
COIN_BONUS_NOTICE_SECONDS = 1.2

# --- Treffer-Feedback: Partikel, Blitze, Erschütterung (`effects.py`) ---
# Reine Deko im Referenzraum, an Wandzeit gekoppelt — nie im Sim-Pfad.
FEEDBACK_MAX_PARTICLES = 260  # Deckel, damit ein Getümmel die Framerate nicht frisst
FEEDBACK_PARTICLE_SPEED: tuple[float, float] = (60.0, 240.0)  # Referenz-px/s
FEEDBACK_DRAG = 1.8  # Partikel bremsen exponentiell ab

HIT_SPARK_COLOR: Color = (255, 240, 180)
HIT_SPARK_COUNT: tuple[int, int] = (4, 7)
HIT_SPARK_TTL: tuple[float, float] = (0.12, 0.28)
HIT_SPARK_RADIUS = 2.0

EXPLOSION_COLORS: tuple[Color, ...] = ((255, 220, 120), (255, 150, 50), (200, 70, 40))
EXPLOSION_COUNT: tuple[int, int] = (12, 18)
EXPLOSION_TTL: tuple[float, float] = (0.3, 0.7)
EXPLOSION_RADIUS = 3.5

PICKUP_SPARK_COUNT: tuple[int, int] = (6, 10)
PICKUP_SPARK_TTL: tuple[float, float] = (0.2, 0.45)
PICKUP_SPARK_RADIUS = 2.5

DAMAGE_FLASH_COLOR: Color = (255, 60, 60)
DAMAGE_FLASH_ALPHA = 110
DAMAGE_FLASH_SECONDS = 0.3
SHIELD_FLASH_COLOR: Color = (120, 190, 255)
SHIELD_FLASH_ALPHA = 90
SHIELD_FLASH_SECONDS = 0.25
DEATH_FLASH_COLOR: Color = (255, 120, 60)
DEATH_FLASH_ALPHA = 150
DEATH_FLASH_SECONDS = 0.6

# Erschütterung als (Ausschlag in Referenz-px, Dauer in Sekunden).
SHAKE_DESTROY: tuple[float, float] = (2.5, 0.12)
SHAKE_CONTACT: tuple[float, float] = (8.0, 0.3)
SHAKE_DEATH: tuple[float, float] = (14.0, 0.6)

# Lebensleiste über getroffenen Gegnern/Meteoriten (`effects.py`, reines Rendering).
# Unsichtbar, solange HP voll sind; nach dem ersten Treffer eine dünne Spur.
HEALTH_BAR_HEIGHT = 2
HEALTH_BAR_GAP = 3  # Abstand über der Hitbox
HEALTH_BAR_INSET = 2  # etwas schmaler als die Hitbox
HEALTH_BAR_TRACK_COLOR: Color = (24, 24, 32)
HEALTH_BAR_FILL_HIGH: Color = (90, 220, 120)
HEALTH_BAR_FILL_LOW: Color = (220, 70, 70)
HEALTH_BAR_FLASH_COLOR: Color = (255, 250, 230)
HEALTH_BAR_FLASH_SECONDS = 0.16
HEALTH_BAR_SHAKE_AMPLITUDE = 2.0  # Referenz-px
HEALTH_BAR_SHAKE_SECONDS = 0.12

# HUD-Zeile leuchtet nach einem Ereignis kurz auf.
HUD_FLASH_SECONDS = 0.35
HUD_FLASH_COLOR: Color = (255, 255, 255)
# Der Tod bleibt kurz stehen, damit Explosion und Blitz sichtbar werden.
DEATH_DELAY_SECONDS = 0.7

# --- Soundeffekte (`sfx.py`, prozedural erzeugt — keine Audiodateien nötig) ---
SFX_VOLUME = 0.35


# --- Shop, Zubehör & Fortschritt (Issue #14) ---
# Speicherort: `METEORITE_DASH_SAVE_DIR` überschreibt das plattformübliche
# Nutzer-Datenverzeichnis (XDG / AppData / Application Support).
SAVE_DIR_ENV = "METEORITE_DASH_SAVE_DIR"
SAVE_APP_DIR = "meteorite-dash"
SAVE_FILENAME = "progress.json"
# 2: Zubehör ist Vorratsware (`accessory_stock`) statt Einmalkauf. Ältere
# Stände werden weiter gelesen — jedes gekaufte Teil zählt als ein Exemplar.
SAVE_FORMAT_VERSION = 2

# Zubehör-Effekte. Preise und Beschreibungen stehen im Katalog in `accessories.py`.
SHIELD_CHARGES = 1  # blockierte Kollisionen pro Lauf
MAGNET_RADIUS = 140.0  # Referenz-px um die Schiffsmitte
MAGNET_PULL_SPEED = 520.0  # Referenz-px/s, muss COIN_SPEED deutlich übersteigen
AMMO_RESERVE_BONUS = 3  # zusätzliche Schüsse im Standard-Magazin
ARMOR_HP_BONUS = 30  # zusätzliche Hüllenpunkte
# Zubehör ist Verbrauchsware: gekauft wird auf Vorrat, ein Lauf verbraucht die
# eingesetzten Teile. Der Deckel hält Lager und Speicherdatei überschaubar.
ACCESSORY_MAX_STOCK = 99

WALLET_TOP_RIGHT: WindowSize = (776, 24)
SHIELD_HUD_TOP_LEFT: WindowSize = (24, 80)
SHIELD_HUD_COLOR: Color = (120, 200, 255)
SHOP_FEEDBACK_SECONDS = 2.5
SHOP_TAB_FONT_SIZE = 28
LOCKED_PREVIEW_ALPHA = 90

# --- Simulation & Determinismus (Issue #34) ---
# Fester Zeitschritt: jede Runde tickt exakt hiermit, egal wie schnell das
# Fenster rendert. Wandzeit bestimmt nur, wie viele Ticks pro Frame laufen.
SIM_TICKS_PER_SECOND = 60
SIM_DT = 1.0 / SIM_TICKS_PER_SECOND
# Deckel gegen die Todesspirale nach einem Hänger; überschüssige Zeit verfällt.
MAX_STEPS_PER_FRAME = 5
# Bei jeder Änderung an Spielregeln/Physik/Spawn erhöhen: Replays älterer
# Versionen bleiben lesbar, werden aber nicht mehr als Ghost/Referenz benutzt.
# 2: pixelgenaue Kollision über Masken statt Rechtecke (`hitbox.py`).
SIM_VERSION = 3
# Seeds sind 32-Bit-Zahlen — kurz genug zum Abtippen ("Rennen gegen Freunde").
SEED_BITS = 32
SEED_ENV = "METEORITE_DASH_SEED"

# --- Adaptiver Schwierigkeits-Director (Free Mode, Issue #33) ---
# Alle Zeiten werden vom Director mit SIM_TICKS_PER_SECOND in feste Ticks
# übersetzt. Die Werte beschreiben den Regelkern; Balancing erfolgt hier.
CONSTANT_DIRECTOR_VERSION = 1
# 3: adaptiver Free Mode läuft jetzt zusätzlich auf der Zeitrampe.
ADAPTIVE_DIRECTOR_VERSION = 3
RAMP_DIRECTOR_VERSION = 1

DIFFICULTY_START_GRACE_SECONDS = 8.0
DIFFICULTY_DAMAGE_HOLD_SECONDS = 6.0
DIFFICULTY_NEAR_MISS_WINDOW_SECONDS = 4.0
DIFFICULTY_COMFORT_STREAK_SECONDS = 10.0
DIFFICULTY_PROBE_SECONDS = 300.0

DIFFICULTY_NEAR_MISS_MARGIN = 24
DIFFICULTY_SAFE_PASS_MASTERY_GAIN = 0.025
DIFFICULTY_SURVIVAL_MASTERY_PER_SECOND = 0.006
DIFFICULTY_COMFORT_MASTERY_PER_SECOND = 0.012
DIFFICULTY_DAMAGE_MASTERY_LOSS = 0.4
DIFFICULTY_DAMAGE_STRESS_GAIN = 1.2
DIFFICULTY_NEAR_MISS_STRESS_GAIN = 0.045
DIFFICULTY_NEAR_MISS_COMBO_CAP = 4
DIFFICULTY_STRESS_DECAY_PER_SECOND = 0.025
DIFFICULTY_TIME_PROBE_MAX = 0.15
DIFFICULTY_AMMO_RELIEF_MAX = 0.05

DIFFICULTY_LOW_HP_RATIO = 0.3
DIFFICULTY_LOW_HP_INTENSITY_CAP = 0.35
DIFFICULTY_RISE_PER_SECOND_MIN = 0.04
DIFFICULTY_RISE_PER_SECOND_MAX = 0.16
DIFFICULTY_FALL_PER_SECOND = 0.35
# Band, in dem der adaptive Director um die Zeitrampe herum moduliert.
DIFFICULTY_ADAPTIVE_SPEED_MULTIPLIER_MAX = 1.75
DIFFICULTY_ADAPTIVE_SPAWN_INTERVAL_MULTIPLIER_MIN = 0.58

# --- Zeitrampe (Issue #32): das Welttempo steigt in jedem Modus mit der Laufzeit ---
# Theoretische Obergrenze — realistisch stirbt man lange vorher. Die Rampe
# verkürzt zugleich die Spawn-Intervalle um denselben Faktor, damit der
# räumliche Abstand der Gefahren gleich bleibt: schneller, nicht leerer.
DIFFICULTY_RAMP_SPEED_MULTIPLIER_MAX = 10.0
# Sekunden bis zur Obergrenze, linear — also rund +0.3 Tempo je Minute.
DIFFICULTY_RAMP_FULL_SECONDS = 1800.0
# Schonzeit am Start: davor bleibt die Rampe bei 1.0.
DIFFICULTY_RAMP_GRACE_SECONDS = 10.0

# Gemeinsamer Deckel über alle Directors zusammen (Rampe x adaptiv).
DIFFICULTY_SPEED_MULTIPLIER_CAP = 10.0
DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_FLOOR = 0.05

# --- Replays (Issue #34) ---
# Replays liegen neben `progress.json`; `last` ist immer der letzte, `best` der
# weiteste Lauf. Namen laufen durch `ReplayStore.path_for` (kein Path-Traversal).
REPLAY_DIR_NAME = "replays"
REPLAY_FORMAT_VERSION = 1
REPLAY_LAST_NAME = "last"
REPLAY_BEST_NAME = "best"

# --- Ghost (Issue #34) ---
# Der Ghost ist der beste gespeicherte Lauf zum selben Seed und läuft als
# zweite Simulation im Gleichschritt mit; nur sein Schiff wird gezeichnet.
GHOST_ALPHA = 110
GHOST_TINT: Color = (150, 210, 255)
GHOST_HUD_COLOR: Color = (150, 210, 255)
GHOST_HUD_TOP_RIGHT: WindowSize = (776, 108)
# Der Vorsprung in Lichtjahren wird zum waagerechten Versatz des Ghost-Schiffs:
# wer weiter ist, schiebt den anderen nach hinten. Weich gesättigt (`tanh`),
# damit große Abstände nicht aus dem Bild laufen; reines Rendering, der
# Ghost-Zustand bleibt unberührt.
GHOST_LEAD_MAX_OFFSET = 220.0  # Referenz-px, Grenzwert des Versatzes
GHOST_LEAD_SOFT_LIGHT_YEARS = 90.0  # Vorsprung, der ~76 % davon erreicht
GHOST_LEAD_MIN_X = 4  # solange er lebt, bleibt der Ghost am linken Rand sichtbar
GHOST_FADE_SECONDS = 2.0  # danach fällt er zurück und blendet aus

# --- Daily Run (Issue #34) ---
# Der Tages-Seed ist ein Hash aus Salt + UTC-Datum: alle Spieler rechnen ihn
# lokal aus, kein Server nötig. Salt ändern = neue Seed-Serie.
DAILY_SEED_SALT = "meteorite-dash-daily"
DAILY_REPLAY_PREFIX = "daily-"
DEATH_MODE_COLOR: Color = (150, 210, 255)

# --- Community-Läufe über Nostr (Issue #34, „Server-Funktion" ohne Server) ---
# Bestläufe gehen als ersetzbares Event (NIP-78, `kind:30078`) an öffentliche
# Relays; `d`-Tag = `NOSTR_APP_TAG:<SIM_VERSION>:<seed>`, Inhalt = Share-Code.
# Fremde Läufe werden vor dem Import mit `headless.verify` nachgespielt.
NOSTR_RELAYS: tuple[str, ...] = (
    "wss://nos.lol",
    "wss://relay.primal.net",
    "wss://nostr.mom",
    "wss://relay.damus.io",
)
NOSTR_RUN_KIND = 30078
NOSTR_APP_TAG = "meteorite-dash"
NOSTR_TIMEOUT = 6.0  # Sekunden pro Relay-Verbindung (verbinden + antworten)
# So lange wartet der Spielstart auf fremde Läufe; danach geht es ohne sie los.
NOSTR_FETCH_TIMEOUT = 3.0
# Relays liefern die *neuesten* N Events, nicht die besten — deshalb großzügig;
# geprüft wird weiteste-zuerst im Hintergrund.
NOSTR_MAX_RUNS = 100
# Härtung gegen ein Relay, das `limit`/EOSE ignoriert und unbegrenzt Events streamt.
NOSTR_MAX_EVENTS_PER_FETCH = 500
NOSTR_MAX_TICKS = 30 * 60 * SIM_TICKS_PER_SECOND  # längere fremde Läufe werden ignoriert
NOSTR_MAX_CONTENT_CHARS = 64_000  # Share-Code-Länge, ab der ein Event verworfen wird
NOSTR_REPLAY_PREFIX = "nostr-"  # Ablage fremder Läufe: `nostr-<seed>-<pubkey8>`
OFFLINE_ENV = "METEORITE_DASH_OFFLINE"  # gesetzt = kein Netz, kein Teilen

# Identität: zufälliger Schlüssel pro Installation, neben `progress.json`.
IDENTITY_FILENAME = "identity.json"
IDENTITY_FORMAT_VERSION = 1
PUBKEY_SHORT_LEN = 8  # Anzeige-Kurzform eines Pubkeys

# Share-Code: kompaktes Binärformat eines Replays (`sharecode.py`).
SHARECODE_VERSION = 2  # 2: Director-Art und -Version im Header

# --- Share-Phrase: drei Wörter als Adresse eines geteilten Laufs (`phrase.py`) ---
PHRASE_WORDS_FILE = "words_de.txt"  # assets/, 2048 Wörter, eingefroren
PHRASE_WORD_COUNT = 3
PHRASE_WORD_BITS = 11  # 2^11 = 2048 Wörter je Position
# Wortliste oder Ableitung geändert -> alte Phrasen ungültig -> erhöhen.
PHRASE_VERSION = 1
NOSTR_SHARE_EXPIRY_SECONDS = 30 * 24 * 60 * 60  # NIP-40: Relays dürfen danach löschen
SHARE_REPLAY_PREFIX = "share-"  # Ablage geholter Codes: `share-<w1>-<w2>-<w3>`

# --- Code eingeben (Szene) ---
CODE_ENTRY_MAX_CHARS = 40
CODE_ENTRY_TITLE_TOP = 90
CODE_ENTRY_EXPLAIN_TOP = 138  # wofür der Code gut ist
CODE_ENTRY_HINT_TOP = 166  # wie er aussieht
CODE_ENTRY_BOX_RECT: tuple[int, int, int, int] = (100, 200, 600, 60)  # Referenz-px
CODE_ENTRY_MESSAGE_TOP = 300
CODE_ENTRY_RESULT_TOP = 360
CODE_ENTRY_ACTIONS_TOP = 400
CODE_ENTRY_FOOTER_TOP = 535
CODE_ENTRY_CURSOR_BLINK_MS = 500

COMMUNITY_STATUS_TOP: int = 344  # Referenz-y der Community-Zeile (im Daily-Block)
COMMUNITY_STATUS_COLOR: Color = (150, 210, 255)

# --- Daily-Bestenliste ---
LEADERBOARD_SIZE = 5
LEADERBOARD_OWN_LABEL = "DU"
LEADERBOARD_TITLE_TOP = 80
LEADERBOARD_SUBTITLE_TOP = 130
LEADERBOARD_STATUS_TOP = 160
LEADERBOARD_HEADER_TOP = 200
LEADERBOARD_ROWS_TOP = 236
LEADERBOARD_ROW_SPACING = 38
LEADERBOARD_OWN_TOP = 460
LEADERBOARD_HINT_TOP = 535
# Referenz-x der Spalten: Rang, Spieler, Lichtjahre, Schiff
LEADERBOARD_COLUMNS: tuple[int, int, int, int] = (140, 200, 400, 560)
