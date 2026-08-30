import os

import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import (
    CAPTION,
    HINT_FONT_SIZE,
    IDENTITY_FILENAME,
    MENU_FONT_NAME,
    MENU_FONT_SIZE,
    NOSTR_FETCH_TIMEOUT,
    OFFLINE_ENV,
    WINDOW_SIZE,
)
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.daily import daily_seed, today_utc
from meteorite_dash.exchange import RunExchange
from meteorite_dash.identity import IdentityStore
from meteorite_dash.persistence import SaveStore, default_save_dir, default_save_path
from meteorite_dash.replay import ReplayStore, RunMode, default_replay_dir
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.scenes.ship_selection import ShipSelection
from meteorite_dash.scenes.shop import ShopScene
from meteorite_dash.simulation import pick_seed, seed_forced
from meteorite_dash.starfield import StarField
from meteorite_dash.viewport import Viewport

_MENU_TRANSITIONS = (Transition.MAIN_MENU, Transition.SHIP_SELECTION, Transition.SHOP)
_GAME_TRANSITIONS = (Transition.START_GAME, Transition.START_DAILY)


class App:
    def __init__(self) -> None:
        pygame.init()
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption(CAPTION)
        store = SaveStore(default_save_path())
        replays = ReplayStore(default_replay_dir())
        exchange = None
        if not os.environ.get(OFFLINE_ENV):
            identity = IdentityStore(default_save_dir() / IDENTITY_FILENAME).load_or_create()
            exchange = RunExchange(identity, replays)
        self.context = GameContext(
            screen=screen,
            clock=pygame.time.Clock(),
            menu_font=pygame.font.SysFont(MENU_FONT_NAME, MENU_FONT_SIZE),
            hint_font=pygame.font.SysFont(MENU_FONT_NAME, HINT_FONT_SIZE),
            music=MusicPlayer(),
            assets=AssetLoader(),
            state=GameState(progress=store.load()),
            starfield=StarField(screen.get_width(), screen.get_height()),
            viewport=Viewport(screen.get_width(), screen.get_height()),
            store=store,
            replays=replays,
            exchange=exchange,
        )

    def run(self) -> None:
        transition = Transition.MAIN_MENU
        menu_music_playing = False
        try:
            while transition is not Transition.QUIT:
                if transition in _MENU_TRANSITIONS and not menu_music_playing:
                    self.context.music.play_menu_loop()
                    menu_music_playing = True

                transition = self._create_scene(transition).run()

                if transition in _GAME_TRANSITIONS:
                    menu_music_playing = False
        finally:
            self.context.music.stop()
            if self.context.exchange is not None:
                self.context.exchange.wait_idle(NOSTR_FETCH_TIMEOUT)
            pygame.quit()

    def _create_scene(self, transition: Transition) -> Scene:
        if transition is Transition.MAIN_MENU:
            return MainMenu(self.context)
        if transition is Transition.SHIP_SELECTION:
            return ShipSelection(self.context)
        if transition is Transition.SHOP:
            return ShopScene(self.context)
        if transition is Transition.START_GAME:
            seed = pick_seed()
            if seed_forced():
                # Erzwungener Seed = Rennen gegen jemanden: dessen Lauf holen.
                self._import_runs(seed)
            return GameScene(self.context, seed=seed)
        if transition is Transition.START_DAILY:
            day = today_utc()
            seed = daily_seed(day)
            self._import_runs(seed)
            return GameScene(self.context, seed=seed, mode=RunMode.DAILY, label=day.isoformat())
        if transition is Transition.DEATH_SCREEN:
            return DeathScene(self.context)
        raise ValueError(f"No scene for transition {transition}")

    def _import_runs(self, seed: int) -> None:
        """Fremde Läufe zum Seed holen, damit `GameScene` sie als Ghost findet —
        höchstens `NOSTR_FETCH_TIMEOUT` lang, sonst ohne sie starten."""
        if self.context.exchange is not None:
            self.context.exchange.wait_for(seed, NOSTR_FETCH_TIMEOUT)
