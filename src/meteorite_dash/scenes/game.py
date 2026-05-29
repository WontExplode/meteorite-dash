import pygame

from meteorite_dash.audio import GAME_MUSIC_ENDED
from meteorite_dash.config import BACKGROUND_COLOR, PLAYER_SIZE, PLAYER_START_POSITION
from meteorite_dash.context import GameContext
from meteorite_dash.player import Player
from meteorite_dash.scenes.base import Scene, Transition


class GameScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)
        image = context.assets.load_ship(context.state.selected_ship_filename, PLAYER_SIZE)
        self.player = Player(image, PLAYER_START_POSITION)

    def on_enter(self) -> None:
        self.context.music.start_game_playlist()

    def on_exit(self) -> None:
        self.context.music.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == GAME_MUSIC_ENDED:
            self.context.music.advance_track()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.finish(Transition.MAIN_MENU)

    def update(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        self.player.update(dt, keys, self.context.screen.get_height())

    def draw(self) -> None:
        self.context.screen.fill(BACKGROUND_COLOR)
        self.player.draw(self.context.screen)
        pygame.display.flip()
