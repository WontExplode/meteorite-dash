import pygame


def main() -> None:
    pygame.init()

    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Meteorite Dash")
    clock = pygame.time.Clock()

    player = pygame.Rect(50, 100, 32, 32)

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
        if keys[pygame.K_DOWN] and player.y < 568:
            player.y += speed * dt

        screen.fill((10, 10, 20))
        pygame.draw.rect(surface=screen, color=(255, 0, 0), rect=player)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
