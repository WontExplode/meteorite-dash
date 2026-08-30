"""Szenen-Framework: Basisklasse mit dem gemeinsamen 60-FPS-Loop und `Transition`.

Jede Szene läuft in `Scene.run()`, bis sie per `finish(transition)` ihren
Nachfolger benennt; `App._create_scene` mappt den `Transition` auf die nächste Szene.
"""

from abc import ABC, abstractmethod
from enum import Enum, auto

import pygame

from meteorite_dash.config import FPS
from meteorite_dash.context import GameContext


class Transition(Enum):
    """Ergebnis einer Szene: sagt der `App`, welche Szene als Nächstes läuft."""

    QUIT = auto()
    MAIN_MENU = auto()
    START_GAME = auto()
    START_DAILY = auto()
    SHIP_SELECTION = auto()
    SHOP = auto()
    DEATH_SCREEN = auto()


class Scene(ABC):
    """Template-method base scene providing the shared 60 FPS event loop."""

    def __init__(self, context: GameContext) -> None:
        self.context = context
        self._transition: Transition | None = None

    def finish(self, transition: Transition) -> None:
        """Beendet den Loop nach dem aktuellen Frame und meldet den Nachfolger."""
        self._transition = transition

    def run(self) -> Transition:
        """Template-Method-Loop: `tick`, Events, `update`, `draw`, bis `finish` fällt.

        Globale Events behandelt die Basis selbst: `QUIT`, `VIDEORESIZE` (Resize über
        den `GameContext`) und Vollbild-Toggle (`F` / `F11`); alles andere geht an
        `handle_event`. `on_exit` läuft auch bei Ausnahmen. Liefert den `Transition`.
        """
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
        """Hook beim Betreten der Szene, vor dem ersten Frame (optional)."""
        pass

    def on_exit(self) -> None:  # noqa: B027  (optional hook)
        """Hook beim Verlassen, auch bei Ausnahmen im Loop (optional)."""
        pass

    def on_resize(self, size: tuple[int, int]) -> None:  # noqa: B027  (optional hook)
        """Hook nach Resize oder Vollbild-Wechsel; `size` ist die neue Fenstergröße."""
        pass

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None:
        """Verarbeitet ein Ereignis, das die Basis nicht global behandelt hat."""
        pass

    def update(self, dt: float) -> None:  # noqa: B027  (optional hook)
        """Rückt den Szenen-Zustand um `dt` Sekunden Wandzeit vor (optional)."""
        pass

    @abstractmethod
    def draw(self) -> None:
        """Zeichnet den Frame; `pygame.display.flip()` gehört zur Szene."""
        raise NotImplementedError
