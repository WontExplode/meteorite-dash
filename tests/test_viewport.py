import random

import pygame

from meteorite_dash.config import (
    ENEMY_SIZE,
    HUNTER_VERTICAL_SPEED,
    METEORITE_SPEED,
    METEORITE_VARIANTS,
    PLAYER_SIZE,
    REFERENCE_SIZE,
)
from meteorite_dash.context import GameContext
from meteorite_dash.entities import spawn_hunter_enemy, spawn_meteorite, spawn_wave_enemy
from meteorite_dash.render import RenderContext
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.starfield import StarField
from meteorite_dash.viewport import Viewport


def test_viewport_is_identity_at_reference() -> None:
    vp = Viewport(800, 600)
    assert (vp.scale_x, vp.scale_y, vp.scale) == (1.0, 1.0, 1.0)
    assert vp.center_x == 400
    assert vp.px(120) == 120
    assert vp.py(240) == 240
    assert vp.s(96) == 96
    assert vp.font_size(42) == 42


def test_viewport_fluid_width_keeps_height_tied_sizes() -> None:
    # Wide-but-same-height window: positions stretch in x, sizes stay constant.
    vp = Viewport(1600, 600)
    assert vp.scale_x == 2.0
    assert vp.scale_y == 1.0
    assert vp.scale == 1.0
    assert vp.center_x == 800
    assert vp.px(400) == 800
    assert vp.py(300) == 300
    assert vp.s(44) == 44


def test_viewport_height_drives_uniform_scale() -> None:
    vp = Viewport(800, 1200)
    assert vp.scale == 2.0
    assert vp.s(44) == 88
    assert vp.py(300) == 600
    assert vp.font_size(42) == 84


def test_viewport_font_size_clamped_to_minimum() -> None:
    vp = Viewport(800, 12)  # scale_y = 0.02
    assert vp.font_size(42) == 1


def test_viewport_font_is_cached_and_rebuilt_on_size_change(context: GameContext) -> None:
    vp = Viewport(800, 600)
    first = vp.font(42)
    assert vp.font(42) is first  # same pixel size -> cached object
    vp.resize(800, 1200)
    bigger = vp.font(42)
    assert bigger is not first  # font_size changed 42 -> 84 -> rebuilt


def test_context_apply_resize_updates_screen_viewport_starfield(context: GameContext) -> None:
    context.apply_resize((1000, 700))
    assert context.screen.get_size() == (1000, 700)
    assert context.viewport.size == (1000, 700)
    assert (context.starfield.width, context.starfield.height) == (1000, 700)


def test_context_apply_resize_clamps_to_minimum(context: GameContext) -> None:
    context.apply_resize((50, 50))
    assert context.screen.get_size() == (320, 240)
    assert context.viewport.size == (320, 240)


def test_context_apply_resize_clamps_each_axis_independently(context: GameContext) -> None:
    # Width above the floor, height below it: only height should be clamped.
    context.apply_resize((1000, 100))
    assert context.screen.get_size() == (1000, 240)


def test_context_apply_resize_ignored_while_fullscreen(context: GameContext) -> None:
    context.toggle_fullscreen()
    fs_size = context.screen.get_size()
    context.apply_resize((1234, 567))
    assert context.screen.get_size() == fs_size  # OS-driven event ignored
    assert context.is_fullscreen is True  # not dropped out of fullscreen
    context.toggle_fullscreen()
    assert context.screen.get_size() == (800, 600)  # _windowed_size not clobbered


def test_context_fullscreen_toggle_round_trip(context: GameContext) -> None:
    desktop = pygame.display.get_desktop_sizes()[0]
    assert context.is_fullscreen is False

    context.toggle_fullscreen()
    assert context.is_fullscreen is True
    assert context.screen.get_size() == desktop
    assert context.viewport.size == desktop

    context.toggle_fullscreen()
    assert context.is_fullscreen is False
    assert context.screen.get_size() == (800, 600)


def test_starfield_resize_rescales_star_positions() -> None:
    field = StarField(800, 600, star_count=10)
    field.stars[0].x = 400.0
    field.stars[0].y = 300.0
    field.resize(1600, 1200)
    assert (field.width, field.height) == (1600, 1200)
    assert field.stars[0].x == 800.0  # 400 * (1600/800)
    assert field.stars[0].y == 600.0  # 300 * (1200/600)


def test_render_context_maps_reference_rect() -> None:
    surface = pygame.Surface((1600, 1200))
    ctx = RenderContext(surface, Viewport(1600, 1200))
    assert ctx.rect(pygame.Rect(100, 50, 40, 20)) == pygame.Rect(200, 100, 80, 40)

    # Breites Fenster: Position in x gestreckt, Größe bleibt höhen-gebunden.
    wide = RenderContext(surface, Viewport(1600, 600))
    assert wide.rect(pygame.Rect(100, 50, 40, 20)) == pygame.Rect(200, 50, 40, 20)
    # Nie kleiner als 1 px, sonst verschwinden winzige Sprites.
    tiny = RenderContext(surface, Viewport(800, 12))
    assert tiny.rect(pygame.Rect(0, 0, 4, 4)).size == (1, 1)


def test_spawn_factories_work_in_reference_space() -> None:
    meteorite = spawn_meteorite(random.Random(0), REFERENCE_SIZE)
    assert meteorite.rect.left == REFERENCE_SIZE[0]
    assert meteorite.rect.width in {variant.radius * 2 for variant in METEORITE_VARIANTS}
    assert meteorite.speed_x == METEORITE_SPEED

    wave = spawn_wave_enemy(random.Random(0), REFERENCE_SIZE)
    assert wave.rect.size == ENEMY_SIZE
    hunter = spawn_hunter_enemy(random.Random(0), REFERENCE_SIZE)
    assert hunter._vertical_speed == HUNTER_VERTICAL_SPEED


def test_game_scene_simulation_ignores_window_size(context: GameContext) -> None:
    context.apply_resize((1600, 1200))  # scale == 2.0
    scene = GameScene(context)
    assert scene.player.rect.size == PLAYER_SIZE
    assert scene.player.rect.topleft == (50, 100)
    assert scene.spawner.area == REFERENCE_SIZE

    # Erst der RenderContext skaliert; die Szene selbst kennt keine Fensterpixel.
    ctx = RenderContext(context.screen, context.viewport)
    assert ctx.rect(scene.player.rect) == pygame.Rect(100, 200, 128, 128)

    # Resize während des Laufs lässt die Simulation unberührt.
    scene.player.set_vertical_position(500)
    context.apply_resize((800, 600))
    scene.on_resize((800, 600))
    assert scene.player.rect.y == 500
    scene.draw()
