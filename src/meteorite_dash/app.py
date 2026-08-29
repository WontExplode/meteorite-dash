import pygame

from meteorite_dash.assets import AssetLoader
from meteorite_dash.audio import MusicPlayer
from meteorite_dash.config import (
    CAPTION,
    HINT_FONT_SIZE,
    MENU_FONT_NAME,
    MENU_FONT_SIZE,
    WINDOW_SIZE,
)
from meteorite_dash.context import GameContext, GameState
from meteorite_dash.persistence import SaveStore, default_save_path
from meteorite_dash.scenes.base import Scene, Transition
from meteorite_dash.scenes.death import DeathScene
from meteorite_dash.scenes.game import GameScene
from meteorite_dash.scenes.main_menu import MainMenu
from meteorite_dash.scenes.ship_selection import ShipSelection
from meteorite_dash.scenes.shop import ShopScene
from meteorite_dash.starfield import StarField
from meteorite_dash.viewport import Viewport

_MENU_TRANSITIONS = (Transition.MAIN_MENU, Transition.SHIP_SELECTION, Transition.SHOP)


class App:
    def __init__(self) -> None:
        pygame.init()
        screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        pygame.display.set_caption(CAPTION)
        store = SaveStore(default_save_path())
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

                if transition is Transition.START_GAME:
                    menu_music_playing = False
        finally:
            self.context.music.stop()
            pygame.quit()

    def _create_scene(self, transition: Transition) -> Scene:
        if transition is Transition.MAIN_MENU:
            return MainMenu(self.context)
        if transition is Transition.SHIP_SELECTION:
            return ShipSelection(self.context)
        if transition is Transition.SHOP:
            return ShopScene(self.context)
        if transition is Transition.START_GAME:
            return GameScene(self.context)
        if transition is Transition.DEATH_SCREEN:
            return DeathScene(self.context)
        raise ValueError(f"No scene for transition {transition}")
