"""Musik und Soundeffekte über `pygame.mixer`.

Die Spiel-Playlist meldet das Ende eines Tracks als `GAME_MUSIC_ENDED`-Userevent;
die Szene ruft dann `advance_track`.
"""

import pygame

from meteorite_dash.assets import sound_path
from meteorite_dash.config import GAME_MUSIC_TRACKS, MENU_MUSIC

GAME_MUSIC_ENDED = pygame.USEREVENT + 1


class MusicPlayer:
    """Encapsulates all pygame.mixer.music handling."""

    def __init__(self) -> None:
        self.track_index = 0

    def play_menu_loop(self) -> None:
        """Spielt die Menümusik als Endlosschleife ohne End-Event."""
        pygame.mixer.music.set_endevent(0)
        pygame.mixer.music.load(sound_path(MENU_MUSIC))
        pygame.mixer.music.play(loops=-1)

    def start_game_playlist(self) -> None:
        """Startet die Spiel-Playlist beim ersten Track und aktiviert `GAME_MUSIC_ENDED`."""
        self.track_index = 0
        pygame.mixer.music.set_endevent(GAME_MUSIC_ENDED)
        self._load_and_play(GAME_MUSIC_TRACKS[self.track_index])

    def play_sound_effect(self, filename: str) -> None:
        """Spielt einen Soundeffekt einmalig ab (unabhängig von der Musik)."""
        pygame.mixer.Sound(sound_path(filename)).play()

    def advance_track(self) -> None:
        """Schaltet zyklisch zum nächsten Track der Spiel-Playlist."""
        self.track_index = (self.track_index + 1) % len(GAME_MUSIC_TRACKS)
        self._load_and_play(GAME_MUSIC_TRACKS[self.track_index])

    def stop(self) -> None:
        """Stoppt die Musik und deaktiviert das End-Event."""
        pygame.mixer.music.stop()
        pygame.mixer.music.set_endevent(0)

    def _load_and_play(self, filename: str) -> None:
        """Lädt eine Musikdatei und spielt sie einmal ab."""
        pygame.mixer.music.load(sound_path(filename))
        pygame.mixer.music.play()
