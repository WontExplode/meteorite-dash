"""Eingaben als Bitmaske pro Simulations-Tick (Issue #34).

Die Simulation sieht nie `pygame.key.get_pressed()`, sondern nur einen
`InputFrame`. Dieselbe Maske wird aufgezeichnet (Replay), wiedergegeben
(Ghost) und in Tests direkt erzeugt — ohne Tastatur.
"""

from enum import IntFlag
from typing import Protocol

import pygame


class KeyStates(Protocol):
    """Minimalschnittstelle von `pygame.key.get_pressed()`: Tastencode -> gedrückt."""

    def __getitem__(self, key: int) -> bool:
        pass


class InputFrame(IntFlag):
    """Eingaben eines Ticks als Bitmaske; `SWAP_WEAPON` ist eine Flanke, der Rest gehalten."""

    NONE = 0
    UP = 1
    DOWN = 2
    FIRE = 4
    # Flanke: genau in dem Tick gesetzt, in dem die Taste gedrückt wurde.
    SWAP_WEAPON = 8


def from_pressed(keys: KeyStates) -> InputFrame:
    """Gehaltene Tasten -> Maske (ohne Flanken; die setzt die Szene aus Events)."""
    frame = InputFrame.NONE
    if keys[pygame.K_UP]:
        frame |= InputFrame.UP
    if keys[pygame.K_DOWN]:
        frame |= InputFrame.DOWN
    if keys[pygame.K_SPACE]:
        frame |= InputFrame.FIRE
    return frame
