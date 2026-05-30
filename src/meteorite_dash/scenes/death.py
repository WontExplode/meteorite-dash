from meteorite_dash.scenes.base import Scene
from meteorite_dash.context import GameContext
from meteorite_dash.scenes.base import Transition
import pygame
from meteorite_dash.config import DEATH_SOUND


class DeathScene(Scene):
    def __init__(self, context: GameContext) -> None:
        super().__init__(context)

    def on_enter(self) -> None:
        self.context.music.play_sound_effect(DEATH_SOUND)

    def on_exit(self) -> None:
        self.context.music.stop()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            self.finish(Transition.MAIN_MENU)
        elif event.type == pygame.QUIT:
            self.finish(Transition.QUIT)