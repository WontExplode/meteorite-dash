from typing import Literal

import pygame

from meteorite_dash.assets import image_path, sound_path
from meteorite_dash.starfield import StarField

GameResult = Literal["menu", "quit"]
GAME_MUSIC_ENDED = pygame.USEREVENT + 1
GAME_MUSIC_TRACKS = ("gamemusic1.mp3", "gamemusic2.mp3", "gamemusic3.mp3")


class Game:
    def __init__(
        self, screen: pygame.Surface, clock: pygame.time.Clock, ship_filename: str
    ) -> None:
        self.screen = screen
        self.clock = clock
        self.player_image = pygame.image.load(image_path(ship_filename)).convert_alpha()
        self.player_image = pygame.transform.scale(self.player_image, (64, 64))
        self.player_image = pygame.transform.rotate(self.player_image, -90)
        self.player = self.player_image.get_rect(topleft=(50, 100))
        self.starfield = StarField(screen.get_width(), screen.get_height())
        self.current_music_index = 0

    def run(self) -> GameResult:
        self._start_music()
        try:
            while True:
                dt = self.clock.tick(60) / 1000

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return "quit"
                    if event.type == GAME_MUSIC_ENDED:
                        self._play_next_music_track()
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        return "menu"

                self._update_player(dt)
                self.starfield.update(dt)
                self._draw()
        finally:
            self._stop_music()

    def _update_player(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
        speed = 300
        movement = int(speed * dt)

        if keys[pygame.K_UP] and self.player.y > 0:
            self.player.y -= movement
        if keys[pygame.K_DOWN] and self.player.y < self.screen.get_height() - self.player.height:
            self.player.y += movement

    def _draw(self) -> None:
        self.screen.fill((10, 10, 20))
        self.starfield.draw(self.screen)
        self.screen.blit(self.player_image, self.player)
        pygame.display.flip()

    def _start_music(self) -> None:
        self.current_music_index = 0
        pygame.mixer.music.set_endevent(GAME_MUSIC_ENDED)
        self._play_current_music_track()

    def _play_current_music_track(self) -> None:
        pygame.mixer.music.load(sound_path(GAME_MUSIC_TRACKS[self.current_music_index]))
        pygame.mixer.music.play()

    def _play_next_music_track(self) -> None:
        self.current_music_index = (self.current_music_index + 1) % len(GAME_MUSIC_TRACKS)
        self._play_current_music_track()

    def _stop_music(self) -> None:
        pygame.mixer.music.stop()
        pygame.mixer.music.set_endevent(0)
