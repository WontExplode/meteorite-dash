from pathlib import Path

import pygame

ASSET_DIR = Path(__file__).parent / "assets" / "images"

def main() -> None:
    pygame.init()

    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Meteorite Dash")
    clock = pygame.time.Clock()

    player_image = pygame.image.load(ASSET_DIR / "CopperShip1.png").convert_alpha()
    player_image = pygame.transform.scale(player_image, (64, 64))
    player_image = pygame.transform.rotate(player_image, -90)
    player = player_image.get_rect(topleft=(50, 100))

    running = True
    while running:
        dt = clock.tick(60) / 1000 # Zeit seit letztem Frame in Sekunden

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

        keys = pygame.key.get_pressed()
        speed = 300
        
        if keys[pygame.K_UP] and player.y > 0:
            player.y -= speed * dt
        if keys[pygame.K_DOWN] and player.y < screen.get_height() - player.height:
            player.y += speed * dt

        screen.fill((10, 10, 20))
        screen.blit(player_image, player)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
