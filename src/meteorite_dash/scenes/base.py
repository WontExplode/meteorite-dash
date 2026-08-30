from abc import ABC, abstractmethod
from enum import Enum, auto

import pygame

from meteorite_dash.config import FPS
from meteorite_dash.context import GameContext


class Transition(Enum):
    QUIT = auto()
    MAIN_MENU = auto()
    START_GAME = auto()
    SHIP_SELECTION = auto()
    SHOP = auto()
    DEATH_SCREEN = auto()


class Scene(ABC):
    """Template-method base scene providing the shared 60 FPS event loop."""

    def __init__(self, context: GameContext) -> None:
        self.context = context
        self._transition: Transition | None = None

    def finish(self, transition: Transition) -> None:
        self._transition = transition

    def run(self) -> Transition:
        self._transition = None
        self.on_enter()
        try:
            while self._transition is None:
                dt = self.context.clock.tick(FPS) / 1000

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.finish(Transition.QUIT)
                    elif event.type == pygame.VIDEORESIZE:
                        self.context.apply_resize(event.size)
                        self.on_resize(self.context.screen.get_size())
                    elif event.type == pygame.KEYDOWN and event.key in (
                        pygame.K_F11,
                        pygame.K_f,
                    ):
                        self.context.toggle_fullscreen()
                        self.on_resize(self.context.screen.get_size())
                    else:
                        self.handle_event(event)
                    if self._transition is not None:
                        break

                if self._transition is not None:
                    break

                self.update(dt)
                self.draw()
        finally:
            self.on_exit()

        assert self._transition is not None
        return self._transition

    def on_enter(self) -> None:  # noqa: B027  (optional hook)
        pass

    def on_exit(self) -> None:  # noqa: B027  (optional hook)
        pass

    def on_resize(self, size: tuple[int, int]) -> None:  # noqa: B027  (optional hook)
        pass

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        pass

    def update(self, dt: float) -> None:  # noqa: B027  (optional hook)
        pass

    @abstractmethod
    def draw(self) -> None:
        raise NotImplementedError
