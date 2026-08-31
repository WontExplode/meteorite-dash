"""Tests für die Hauptmenü-Deko (`menu_fx.py`) und das Menü-Zeichnen."""

from random import Random

import pygame

from meteorite_dash import menu_fx
from meteorite_dash.context import GameContext
from meteorite_dash.menu_fx import FxMeteorite, MenuFX
from meteorite_dash.scenes.main_menu import MainMenu

_DT = 1 / 60


def test_fx_spawns_meteorites_and_respects_cap() -> None:
    fx = MenuFX([], rng=Random(1))
    spawned = False
    for _ in range(20 * 60):
        fx.update(_DT)
        spawned = spawned or bool(fx.meteorites)
        assert len(fx.meteorites) <= menu_fx._MAX_METEORITES
    assert spawned


def test_meteorite_bounces_off_target_and_kicks_it() -> None:
    target_rect = pygame.Rect(300, 280, 200, 40)
    fx = MenuFX([target_rect], rng=Random(2))
    meteorite = FxMeteorite(
        x=560.0,
        y=300.0,
        vel_x=-120.0,
        vel_y=0.0,
        diameter=40,
        image_name="AsteroidTiny.png",
        angle=0.0,
        spin=0.0,
    )
    fx.meteorites.append(meteorite)

    bounced = False
    for _ in range(3 * 60):
        fx.update(_DT)
        if meteorite.vel_x > 0:
            bounced = True
            break
    assert bounced
    # Der Impuls stößt das Ziel an; die Feder lenkt es aus.
    target = fx.targets[0]
    assert target.vel_x != 0.0 or target.offset_x != 0.0
    assert fx.particles  # Funken am Aufschlagpunkt


def test_enemy_shoots_down_meteorite() -> None:
    fx = MenuFX([], rng=Random(3))
    enemy = fx.enemies[0]
    enemy.cooldown = 0.0
    meteorite = FxMeteorite(
        x=enemy.x + 200.0,
        y=enemy.y,
        vel_x=-60.0,
        vel_y=0.0,
        diameter=40,
        image_name="AsteroidTiny.png",
        angle=0.0,
        spin=0.0,
    )
    fx.meteorites.append(meteorite)

    fx.update(_DT)
    assert fx.projectiles  # ausgerichtet -> Schuss

    for _ in range(10 * 60):
        fx.update(_DT)
        if meteorite not in fx.meteorites:
            break
    assert meteorite not in fx.meteorites
    assert meteorite.x > 0  # abgeschossen, bevor er links entkommen konnte
    assert fx.particles


def test_main_menu_update_and_draw_run_headless(context: GameContext) -> None:
    menu = MainMenu(context)
    # Ein Ziel je Menüpunkt plus Titel.
    assert len(menu.fx.targets) == len(menu._collision_targets())
    for _ in range(10):
        menu.update(_DT)
        menu.draw()
