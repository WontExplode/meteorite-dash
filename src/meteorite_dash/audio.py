import pygame

from meteorite_dash.assets import sound_path
from meteorite_dash.config import GAME_MUSIC_TRACKS, MENU_MUSIC

GAME_MUSIC_ENDED = pygame.USEREVENT + 1


class MusicPlayer:
    """Encapsulates all pygame.mixer.music handling."""

    def __init__(self) -> None:
        self.track_index = 0

    def play_menu_loop(self) -> None:
        pygame.mixer.music.set_endevent(0)
        pygame.mixer.music.load(sound_path(MENU_MUSIC))
        pygame.mixer.music.play(loops=-1)

    def start_game_playlist(self) -> None:
        self.track_index = 0
        pygame.mixer.music.set_endevent(GAME_MUSIC_ENDED)
        self._load_and_play(GAME_MUSIC_TRACKS[self.track_index])
    
    def play_sound_effect(self, filename: str) -> None:
        pygame.mixer.Sound(sound_path(filename)).play()

    def advance_track(self) -> None:
        self.track_index = (self.track_index + 1) % len(GAME_MUSIC_TRACKS)
        self._load_and_play(GAME_MUSIC_TRACKS[self.track_index])

    def stop(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.music.set_endevent(0)

    def _load_and_play(self, filename: str) -> None:
        pygame.mixer.music.load(sound_path(filename))
        pygame.mixer.music.play()
