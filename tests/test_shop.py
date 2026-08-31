"""Shop-Szene, Schiffsauswahl mit Sperren und Zubehör-Effekte im Spiel (Issue #14)."""

from pathlib import Path

import pygame
import pytest

from meteorite_dash.accessories import ACCESSORIES, ACCESSORIES_BY_ID
from meteorite_dash.app import App
from meteorite_dash.coins import Coin, CoinFormation
from meteorite_dash.combat import absorb_contact
from meteorite_dash.config import (
    AMMO_RESERVE_BONUS,
    ARMOR_HP_BONUS,
    COIN_RADIUS,
    MENU_ITEMS,
    SAVE_DIR_ENV,
    SAVE_FILENAME,
    SHIELD_CHARGES,
    STANDARD_WEAPON_MAX_AMMO,
)
from meteorite_dash.context import GameContext
from meteorite_dash.entities import Entity, Meteorite
from meteorite_dash.hitbox import solid
from meteorite_dash.inputs import InputFrame
from meteorite_dash.persistence import SaveStore
from meteorite_dash.player import Player
from meteorite_dash.progress import Progress
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.loadout import LoadoutScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.scenes.ship_selection import ShipSelection
from meteorite_dash.scenes.shop import TABS, ShopScene, ShopTab
from meteorite_dash.ships import SHIPS, SHIPS_BY_NAME, TINTS, TINTS_BY_ID, ShipSpec
from meteorite_dash.weapons import WeaponLoadout

ALLROUNDER = SHIPS_BY_NAME["Allrounder"]
BRAWLER = SHIPS_BY_NAME["Brawler"]
RACER = SHIPS_BY_NAME["Racer"]
BRAWLER_INDEX = SHIPS.index(BRAWLER)
RACER_INDEX = SHIPS.index(RACER)
SHIELD = ACCESSORIES_BY_ID["shield"]
MAGNET = ACCESSORIES_BY_ID["magnet"]
ARMOR = ACCESSORIES_BY_ID["armor"]
AMMO_RESERVE = ACCESSORIES_BY_ID["ammo_reserve"]
GOLD = TINTS_BY_ID["gold"]


def _keydown(key: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, key=key)


def _press(scene: Scene, *keys: int) -> None:
    for key in keys:
        scene.handle_event(_keydown(key))


def _goto_tab(shop: ShopScene, tab: ShopTab) -> None:
    while shop.tab is not tab:
        _press(shop, pygame.K_RIGHT)


def _goto_row(shop: ShopScene, row: int) -> None:
    while shop.row_index != row:
        _press(shop, pygame.K_DOWN)


def _goto_loadout_row(scene: LoadoutScene, row: int) -> None:
    while scene.row_index != row:
        _press(scene, pygame.K_DOWN)


def _spec(accessory_slots: int = 1) -> ShipSpec:
    return ShipSpec(
        name="Testschiff",
        sprite="CopperShip1.png",
        tint=None,
        mass=1.0,
        thrust=1200.0,
        hull=100.0,
        weapon_slots=1,
        accessory_slots=accessory_slots,
    )


def _coin(x: int, y: int) -> Coin:
    return Coin(pygame.Rect(x, y, COIN_RADIUS * 2, COIN_RADIUS * 2), speed_x=0.0)


# --- Hauptmenü ------------------------------------------------------------------


def test_main_menu_has_shop_entry(context: GameContext) -> None:
    menu = MainMenu(context)
    shop_index = [action for _, action in MENU_ITEMS].index("shop")
    for _ in range(shop_index):
        menu.handle_event(_keydown(pygame.K_DOWN))
    menu.handle_event(_keydown(pygame.K_RETURN))
    assert menu._transition is Transition.SHOP


# --- Shop: Navigation ---------------------------------------------------------------


def test_shop_tabs_wrap_and_reset_row(context: GameContext) -> None:
    shop = ShopScene(context)
    assert shop.tab is ShopTab.SHIPS
    _press(shop, pygame.K_DOWN)
    assert shop.row_index == 1
    _press(shop, pygame.K_LEFT)
    assert shop.tab is TABS[-1]
    assert shop.row_index == 0
    _press(shop, pygame.K_RIGHT)
    assert shop.tab is ShopTab.SHIPS


def test_shop_rows_wrap_per_tab(context: GameContext) -> None:
    shop = ShopScene(context)
    _press(shop, pygame.K_UP)
    assert shop.row_index == len(SHIPS) - 1
    _goto_tab(shop, ShopTab.TINTS)
    _press(shop, pygame.K_UP)
    assert shop.row_index == len(TINTS)  # Zeile 0 = Standardfarbe
    assert len(shop.rows()) == len(TINTS) + 1


def test_shop_escape_returns_to_menu(context: GameContext) -> None:
    shop = ShopScene(context)
    _press(shop, pygame.K_ESCAPE)
    assert shop._transition is Transition.MAIN_MENU


def test_shop_draws_every_tab(context: GameContext) -> None:
    shop = ShopScene(context)
    for tab in TABS:
        _goto_tab(shop, tab)
        shop.draw()
    shop.update(0.1)


# --- Shop: Schiffe -------------------------------------------------------------------


def test_shop_buys_ship_and_selects_it(context: GameContext) -> None:
    progress = context.state.progress
    progress.coins = BRAWLER.price + 5
    shop = ShopScene(context)
    _goto_row(shop, BRAWLER_INDEX)
    _press(shop, pygame.K_RETURN)
    assert progress.is_ship_unlocked(BRAWLER)
    assert progress.coins == 5
    assert context.state.selected_ship_index == BRAWLER_INDEX
    assert shop.rows()[BRAWLER_INDEX].status == "Ausgewählt"


def test_shop_refuses_ship_without_coins(context: GameContext) -> None:
    progress = context.state.progress
    progress.coins = BRAWLER.price - 1
    shop = ShopScene(context)
    _goto_row(shop, BRAWLER_INDEX)
    _press(shop, pygame.K_RETURN)
    assert not progress.is_ship_unlocked(BRAWLER)
    assert progress.coins == BRAWLER.price - 1
    assert context.state.selected_ship_index == 0
    assert "Nicht genug Münzen" in shop._feedback
    assert shop.rows()[BRAWLER_INDEX].status == f"{BRAWLER.price} Münzen"


def test_shop_selects_unlocked_ship_for_free(context: GameContext) -> None:
    progress = context.state.progress
    progress.unlocked_ships.add(BRAWLER.name)
    progress.coins = 3
    shop = ShopScene(context)
    _goto_row(shop, BRAWLER_INDEX)
    _press(shop, pygame.K_RETURN)
    assert context.state.selected_ship_index == BRAWLER_INDEX
    assert progress.coins == 3


# --- Shop: Zubehör ---------------------------------------------------------------------


def test_shop_stocks_accessory_without_equipping(context: GameContext) -> None:
    progress = context.state.progress
    progress.coins = SHIELD.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.ACCESSORIES)
    _goto_row(shop, ACCESSORIES.index(SHIELD))
    _press(shop, pygame.K_RETURN)
    assert progress.accessory_count(SHIELD) == 1
    # Eingesetzt wird erst vor dem Lauf, in der LoadoutScene.
    assert not progress.is_equipped(ALLROUNDER, SHIELD)
    assert progress.coins == 0
    assert shop.rows()[ACCESSORIES.index(SHIELD)].status == f"x1   {SHIELD.price} Münzen"


def test_shop_buys_same_accessory_repeatedly(context: GameContext) -> None:
    progress = context.state.progress
    progress.coins = 3 * SHIELD.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.ACCESSORIES)
    _goto_row(shop, ACCESSORIES.index(SHIELD))
    _press(shop, pygame.K_RETURN, pygame.K_RETURN, pygame.K_RETURN)
    assert progress.accessory_count(SHIELD) == 3
    assert progress.coins == 0
    assert shop._feedback == "Gekauft: Schild — Vorrat 3"

    _press(shop, pygame.K_RETURN)
    assert progress.accessory_count(SHIELD) == 3
    assert "Nicht genug Münzen" in shop._feedback


def test_shop_stocks_accessory_for_ship_without_slots(context: GameContext) -> None:
    progress = context.state.progress
    progress.unlocked_ships.add(RACER.name)
    context.state.selected_ship_index = RACER_INDEX
    progress.coins = MAGNET.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.ACCESSORIES)
    _goto_row(shop, ACCESSORIES.index(MAGNET))
    _press(shop, pygame.K_RETURN)
    assert progress.accessory_count(MAGNET) == 1
    assert progress.equipped_accessories(RACER) == []


# --- Shop: Farben -----------------------------------------------------------------------


def test_shop_buys_tint_and_applies_it(context: GameContext) -> None:
    progress = context.state.progress
    progress.coins = GOLD.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.TINTS)
    _goto_row(shop, 1 + TINTS.index(GOLD))
    _press(shop, pygame.K_RETURN)
    assert progress.owns_tint(GOLD)
    assert progress.active_tint(ALLROUNDER) is GOLD
    assert shop.rows()[1 + TINTS.index(GOLD)].status == "Aktiv"
    assert shop.rows()[0].status == "Kostenlos"


def test_shop_default_tint_row_restores_ship_color(context: GameContext) -> None:
    progress = context.state.progress
    progress.owned_tints.add(GOLD.id)
    progress.apply_tint(ALLROUNDER, GOLD)
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.TINTS)
    _press(shop, pygame.K_RETURN)
    assert progress.active_tint(ALLROUNDER) is None
    assert shop.rows()[0].status == "Aktiv"


def test_shop_preview_follows_highlighted_tint(context: GameContext) -> None:
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.TINTS)
    assert shop._preview_target() == (ALLROUNDER, ALLROUNDER.tint)
    _press(shop, pygame.K_DOWN)
    assert shop._preview_target() == (ALLROUNDER, TINTS[0].color)


# --- Shop: Persistenz -------------------------------------------------------------------


def test_shop_saves_after_purchase(context: GameContext, tmp_path: Path) -> None:
    path = tmp_path / SAVE_FILENAME
    context.store = SaveStore(path)
    context.state.progress.coins = GOLD.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.TINTS)
    _goto_row(shop, 1 + TINTS.index(GOLD))
    _press(shop, pygame.K_RETURN)
    assert SaveStore(path).load() == context.state.progress


def test_shop_without_store_does_not_write(context: GameContext) -> None:
    assert context.store is None
    context.state.progress.coins = GOLD.price
    shop = ShopScene(context)
    _goto_tab(shop, ShopTab.TINTS)
    _press(shop, pygame.K_DOWN, pygame.K_RETURN)
    context.save_progress()  # darf ohne Store nichts tun und nicht werfen


# --- Ausrüstung vor dem Lauf -----------------------------------------------------------


def _loadout(context: GameContext, start: Transition = Transition.START_GAME) -> LoadoutScene:
    return LoadoutScene(context, start=start)


def test_loadout_equips_from_stock_and_starts(context: GameContext) -> None:
    progress = context.state.progress
    progress.accessory_stock[SHIELD.id] = 2
    scene = _loadout(context)
    _goto_loadout_row(scene, ACCESSORIES.index(SHIELD))
    _press(scene, pygame.K_SPACE)
    assert progress.is_equipped(ALLROUNDER, SHIELD)
    # Eingesetzt heißt noch nicht verbraucht: das Lager bleibt voll.
    assert progress.accessory_count(SHIELD) == 2
    assert scene.rows()[ACCESSORIES.index(SHIELD)][1] == "Platz 1   x2"

    _press(scene, pygame.K_SPACE)
    assert not progress.is_equipped(ALLROUNDER, SHIELD)
    _press(scene, pygame.K_SPACE, pygame.K_RETURN)
    assert scene._transition is Transition.START_GAME


def test_loadout_daily_starts_the_daily_run(context: GameContext) -> None:
    scene = _loadout(context, Transition.START_DAILY)
    _press(scene, pygame.K_RETURN)
    assert scene._transition is Transition.START_DAILY


def test_loadout_escape_returns_to_menu_without_using_stock(context: GameContext) -> None:
    context.state.progress.accessory_stock[SHIELD.id] = 1
    scene = _loadout(context)
    _goto_loadout_row(scene, ACCESSORIES.index(SHIELD))
    _press(scene, pygame.K_SPACE, pygame.K_ESCAPE)
    assert scene._transition is Transition.MAIN_MENU
    assert context.state.progress.accessory_count(SHIELD) == 1


def test_loadout_reports_empty_stock_and_full_slots(context: GameContext) -> None:
    progress = context.state.progress
    progress.accessory_stock[SHIELD.id] = 1
    scene = _loadout(context)
    _goto_loadout_row(scene, ACCESSORIES.index(MAGNET))
    _press(scene, pygame.K_SPACE)
    assert not progress.is_equipped(ALLROUNDER, MAGNET)
    assert "ist alle" in scene._feedback
    assert scene.rows()[ACCESSORIES.index(MAGNET)][1] == f"leer   {MAGNET.price} Münzen"

    # Allrounder hat genau einen Platz: das zweite Teil passt nicht mehr.
    progress.accessory_stock[MAGNET.id] = 1
    _goto_loadout_row(scene, ACCESSORIES.index(SHIELD))
    _press(scene, pygame.K_SPACE)
    _goto_loadout_row(scene, ACCESSORIES.index(MAGNET))
    _press(scene, pygame.K_SPACE)
    assert not progress.is_equipped(ALLROUNDER, MAGNET)
    assert "Zubehörplätze" in scene._feedback
    scene.draw()
    scene.update(0.1)


def test_loadout_rows_wrap(context: GameContext) -> None:
    scene = _loadout(context)
    _press(scene, pygame.K_UP)
    assert scene.row_index == len(ACCESSORIES) - 1
    _press(scene, pygame.K_DOWN)
    assert scene.row_index == 0


def test_game_scene_consumes_the_loadout(context: GameContext, tmp_path: Path) -> None:
    context.store = SaveStore(tmp_path / SAVE_FILENAME)
    progress = context.state.progress
    progress.accessory_stock[ARMOR.id] = 2
    progress.toggle_accessory(ALLROUNDER, ARMOR)

    scene = GameScene(context)
    assert scene.sim.config.accessories == (ARMOR.id,)
    assert scene.sim.player.max_hp == ALLROUNDER.hp + ARMOR_HP_BONUS
    assert progress.accessory_count(ARMOR) == 1
    # Der Abzug steht sofort auf der Platte, nicht erst am Ende des Laufs.
    assert SaveStore(tmp_path / SAVE_FILENAME).load().accessory_count(ARMOR) == 1

    second = GameScene(context)
    assert second.sim.config.accessories == (ARMOR.id,)
    assert progress.accessory_count(ARMOR) == 0
    # Vorrat leer: der nächste Lauf startet ohne Zubehör.
    third = GameScene(context)
    assert third.sim.config.accessories == ()
    assert third.sim.player.max_hp == ALLROUNDER.hp


def test_spectating_does_not_consume_stock(context: GameContext) -> None:
    progress = context.state.progress
    progress.accessory_stock[SHIELD.id] = 1
    progress.toggle_accessory(ALLROUNDER, SHIELD)
    played = GameScene(context)
    played.step(InputFrame.NONE)
    replay = played.recorder.finish(played.sim)

    progress.accessory_stock[SHIELD.id] = 1
    GameScene(context, spectate=replay)
    assert progress.accessory_count(SHIELD) == 1


def test_app_maps_loadout_transitions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(SAVE_DIR_ENV, str(tmp_path))
    app = App()
    try:
        scenes = {
            Transition.LOADOUT_FREE: Transition.START_GAME,
            Transition.LOADOUT_DAILY: Transition.START_DAILY,
            Transition.LOADOUT_RACE: Transition.START_RACE,
        }
        for transition, start in scenes.items():
            scene = app._create_scene(transition)
            assert isinstance(scene, LoadoutScene)
            assert scene.start is start
    finally:
        pygame.quit()


# --- Schiffsauswahl mit Sperren --------------------------------------------------------


def test_ship_selection_confirms_unlocked_ship(context: GameContext) -> None:
    context.state.progress.unlocked_ships.add(BRAWLER.name)
    selection = ShipSelection(context)
    while selection.cursor != BRAWLER_INDEX:
        _press(selection, pygame.K_RIGHT)
    _press(selection, pygame.K_RETURN)
    assert context.state.selected_ship_index == BRAWLER_INDEX
    assert selection._transition is Transition.MAIN_MENU


def test_ship_selection_blocks_locked_ship(context: GameContext) -> None:
    selection = ShipSelection(context)
    while selection.cursor != BRAWLER_INDEX:
        _press(selection, pygame.K_RIGHT)
    _press(selection, pygame.K_RETURN)
    assert context.state.selected_ship_index == 0
    assert selection._transition is None
    assert str(BRAWLER.price) in selection._feedback
    selection.draw()
    selection.update(0.1)


# --- Zubehör-Effekte: Bausteine ----------------------------------------------------------


def test_player_extra_hp() -> None:
    player = Player((50, 100), _spec(), extra_hp=ARMOR_HP_BONUS)
    assert player.max_hp == _spec().hp + ARMOR_HP_BONUS
    assert player.hp == player.max_hp
    with pytest.raises(ValueError):
        Player((50, 100), _spec(), extra_hp=-1)


def test_weapon_loadout_standard_ammo_bonus() -> None:
    loadout = WeaponLoadout(1, standard_ammo_bonus=AMMO_RESERVE_BONUS)
    assert loadout.active.ammo == STANDARD_WEAPON_MAX_AMMO + AMMO_RESERVE_BONUS
    loadout.fire()
    loadout.refill_standard()
    assert loadout.active.ammo == STANDARD_WEAPON_MAX_AMMO + AMMO_RESERVE_BONUS
    assert WeaponLoadout(1).active.ammo == STANDARD_WEAPON_MAX_AMMO
    with pytest.raises(ValueError):
        WeaponLoadout(1, standard_ammo_bonus=-1)


def test_absorb_contact_removes_hazard_without_damage() -> None:
    player = solid(pygame.Rect(50, 100, 64, 64))
    hit = Meteorite(player.rect.copy(), speed_x=0.0, hp=10, contact_damage=50)
    far = Meteorite(pygame.Rect(600, 100, 40, 40), speed_x=0.0, hp=10, contact_damage=50)
    entities: list[Entity] = [hit, far]
    assert absorb_contact(player, entities) is True
    assert entities == [far]
    assert absorb_contact(player, entities) is False
    assert entities == [far]


def test_coin_pull_toward_does_not_overshoot() -> None:
    coin = _coin(200, 100)
    target = (coin.rect.centerx - 30, coin.rect.centery)
    coin.pull_toward(target, step=10.0)
    assert coin.rect.centerx == target[0] + 20
    coin.pull_toward(target, step=100.0)
    assert coin.rect.center == target
    coin.pull_toward(target, step=100.0)  # bereits am Ziel: keine Division durch null
    assert coin.rect.center == target


def test_formation_attract_only_within_radius() -> None:
    near = _coin(150, 100)
    far = _coin(600, 100)
    formation = CoinFormation([near, far], bonus=0)
    target = (100 + COIN_RADIUS, 100 + COIN_RADIUS)
    formation.attract(target, radius=100.0, step=10.0)
    assert near.rect.x == 140
    assert far.rect.x == 600


# --- Zubehör-Effekte: GameScene --------------------------------------------------------


def _equip(context: GameContext, *ids: str) -> None:
    progress = context.state.progress
    progress.unlocked_ships.add(BRAWLER.name)
    context.state.selected_ship_index = BRAWLER_INDEX
    for acc_id in ids:
        progress.accessory_stock[acc_id] = 1
        progress.toggle_accessory(BRAWLER, ACCESSORIES_BY_ID[acc_id])


def test_game_scene_without_accessories_uses_base_values(context: GameContext) -> None:
    scene = GameScene(context)
    assert scene.sim.player.max_hp == ALLROUNDER.hp
    assert scene.sim.loadout.active.ammo == STANDARD_WEAPON_MAX_AMMO
    assert scene.sim.shield_charges == 0
    assert scene.sim.magnet_enabled is False


def test_game_scene_applies_armor_and_ammo_reserve(context: GameContext) -> None:
    _equip(context, ARMOR.id, AMMO_RESERVE.id)
    scene = GameScene(context)
    assert scene.sim.player.max_hp == BRAWLER.hp + ARMOR_HP_BONUS
    assert scene.sim.loadout.active.ammo == STANDARD_WEAPON_MAX_AMMO + AMMO_RESERVE_BONUS


def test_game_scene_shield_blocks_first_hit(context: GameContext) -> None:
    _equip(context, SHIELD.id)
    scene = GameScene(context)
    assert scene.sim.shield_charges == SHIELD_CHARGES

    scene.sim.entities.append(
        Meteorite(scene.sim.player.rect.copy(), 0.0, hp=10, contact_damage=40)
    )
    scene.step(InputFrame.NONE)
    assert scene.sim.player.hp == scene.sim.player.max_hp
    assert scene.sim.entities == []
    assert scene.sim.shield_charges == SHIELD_CHARGES - 1

    scene.sim.shield_charges = 0
    scene.sim.entities.append(
        Meteorite(scene.sim.player.rect.copy(), 0.0, hp=10, contact_damage=40)
    )
    scene.step(InputFrame.NONE)
    assert scene.sim.player.hp == scene.sim.player.max_hp - 40
    scene.draw()


def test_game_scene_magnet_pulls_nearby_coins(context: GameContext) -> None:
    _equip(context, MAGNET.id)
    scene = GameScene(context)
    assert scene.sim.magnet_enabled
    player_center = scene.sim.player.rect.center
    coin = _coin(player_center[0] + 90, player_center[1] - COIN_RADIUS)
    scene.sim.formations.append(CoinFormation([coin], bonus=0))
    start_x = coin.rect.centerx
    scene.step(InputFrame.NONE)
    assert coin.rect.centerx < start_x


def test_game_scene_uses_progress_tint(context: GameContext) -> None:
    progress = context.state.progress
    progress.owned_tints.add(GOLD.id)
    progress.apply_tint(ALLROUNDER, GOLD)
    scene = GameScene(context)
    expected = context.assets.load_ship(ALLROUNDER.sprite, scene.sim.player.rect.size, GOLD.color)
    assert scene.ship_image(scene.sim.player.rect.size) is expected


def test_game_scene_exit_saves_wallet(context: GameContext, tmp_path: Path) -> None:
    path = tmp_path / SAVE_FILENAME
    context.store = SaveStore(path)
    context.state.progress.coins = 10
    scene = GameScene(context)
    scene.sim.coins_collected = 7
    scene.on_exit()
    assert SaveStore(path).load().coins == 17


def test_progress_default_in_game_state(context: GameContext) -> None:
    assert isinstance(context.state.progress, Progress)
