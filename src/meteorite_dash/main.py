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

        if keys[pygame.K_UP]:
            player.y -= speed * dt
        if keys[pygame.K_DOWN]:
            player.y += speed * dt

        screen.fill((10, 10, 20))
        pygame.draw.rect(screen, (255, 0, 0), player)
        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
