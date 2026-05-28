from typing import Literal

import pygame

from meteorite_dash.assets import SHIP_IMAGES, image_path
from meteorite_dash.game import Game

WindowSize = tuple[int, int]
MenuAction = Literal["start", "ship", "quit"]

WINDOW_SIZE: WindowSize = (800, 600)
BACKGROUND_COLOR = (10, 10, 20)
TEXT_COLOR = (220, 220, 230)
SELECTED_TEXT_COLOR = (255, 210, 80)
MENU_ITEMS: tuple[tuple[str, MenuAction], ...] = (
    ("Start", "start"),
    ("Raumschiff auswählen", "ship"),
    ("Beenden", "quit"),
)


def main() -> None:
    pygame.init()

    try:
        screen = pygame.display.set_mode(WINDOW_SIZE)
        pygame.display.set_caption("Meteorite Dash")
        clock = pygame.time.Clock()
        menu_font = pygame.font.SysFont("arial", 42)
        hint_font = pygame.font.SysFont("arial", 22)

        selected_menu_index = 0
        selected_ship_index = 0
        running = True

        while running:
            action, selected_menu_index = run_main_menu(
                screen=screen,
                clock=clock,
                menu_font=menu_font,
                hint_font=hint_font,
                selected_menu_index=selected_menu_index,
                selected_ship_filename=SHIP_IMAGES[selected_ship_index],
            )

            if action == "start":
                game = Game(
                    screen=screen,
                    clock=clock,
                    ship_filename=SHIP_IMAGES[selected_ship_index],
                )
                if game.run() == "quit":
                    running = False
            elif action == "ship":
                selected_ship_index, should_quit = run_ship_selection(
                    screen=screen,
                    clock=clock,
                    menu_font=menu_font,
                    hint_font=hint_font,
                    selected_ship_index=selected_ship_index,
                )
                if should_quit:
                    running = False
            else:
                running = False
    finally:
        pygame.quit()


def run_main_menu(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    menu_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    selected_menu_index: int,
    selected_ship_filename: str,
) -> tuple[MenuAction, int]:
    while True:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return "quit", selected_menu_index
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    selected_menu_index = (selected_menu_index - 1) % len(MENU_ITEMS)
                elif event.key == pygame.K_DOWN:
                    selected_menu_index = (selected_menu_index + 1) % len(MENU_ITEMS)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                    return MENU_ITEMS[selected_menu_index][1], selected_menu_index

        draw_main_menu(
            screen=screen,
            menu_font=menu_font,
            hint_font=hint_font,
            selected_menu_index=selected_menu_index,
            selected_ship_filename=selected_ship_filename,
        )


def draw_main_menu(
    screen: pygame.Surface,
    menu_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    selected_menu_index: int,
    selected_ship_filename: str,
) -> None:
    screen.fill(BACKGROUND_COLOR)
    center_x = screen.get_width() // 2

    title = menu_font.render("Meteorite Dash", True, TEXT_COLOR)
    title_rect = title.get_rect(center=(center_x, 120))
    screen.blit(title, title_rect)

    for index, (label, _) in enumerate(MENU_ITEMS):
        color = SELECTED_TEXT_COLOR if index == selected_menu_index else TEXT_COLOR
        text = menu_font.render(label, True, color)
        text_rect = text.get_rect(center=(center_x, 240 + index * 70))
        screen.blit(text, text_rect)

    selected_ship = hint_font.render(f"Ausgewählt: {selected_ship_filename}", True, TEXT_COLOR)
    selected_ship_rect = selected_ship.get_rect(center=(center_x, 500))
    screen.blit(selected_ship, selected_ship_rect)

    hint = hint_font.render("Pfeiltasten: wählen  Enter: bestätigen", True, TEXT_COLOR)
    hint_rect = hint.get_rect(center=(center_x, 535))
    screen.blit(hint, hint_rect)

    pygame.display.flip()


def run_ship_selection(
    screen: pygame.Surface,
    clock: pygame.time.Clock,
    menu_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    selected_ship_index: int,
) -> tuple[int, bool]:
    ship_previews = [
        pygame.transform.rotate(
            pygame.transform.scale(
                pygame.image.load(image_path(ship_filename)).convert_alpha(),
                (96, 96),
            ),
            -90,
        )
        for ship_filename in SHIP_IMAGES
    ]

    while True:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return selected_ship_index, True
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_LEFT, pygame.K_UP):
                    selected_ship_index = (selected_ship_index - 1) % len(SHIP_IMAGES)
                elif event.key in (pygame.K_RIGHT, pygame.K_DOWN):
                    selected_ship_index = (selected_ship_index + 1) % len(SHIP_IMAGES)
                elif event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_ESCAPE):
                    return selected_ship_index, False

        draw_ship_selection(
            screen=screen,
            menu_font=menu_font,
            hint_font=hint_font,
            selected_ship_index=selected_ship_index,
            ship_previews=ship_previews,
        )


def draw_ship_selection(
    screen: pygame.Surface,
    menu_font: pygame.font.Font,
    hint_font: pygame.font.Font,
    selected_ship_index: int,
    ship_previews: list[pygame.Surface],
) -> None:
    screen.fill(BACKGROUND_COLOR)
    center_x = screen.get_width() // 2

    title = menu_font.render("Raumschiff auswählen", True, TEXT_COLOR)
    title_rect = title.get_rect(center=(center_x, 120))
    screen.blit(title, title_rect)

    start_x = center_x - 120
    for index, ship_preview in enumerate(ship_previews):
        x = start_x + index * 240
        ship_rect = ship_preview.get_rect(center=(x, 280))
        screen.blit(ship_preview, ship_rect)

        color = SELECTED_TEXT_COLOR if index == selected_ship_index else TEXT_COLOR
        label = hint_font.render(SHIP_IMAGES[index], True, color)
        label_rect = label.get_rect(center=(x, 365))
        screen.blit(label, label_rect)

        if index == selected_ship_index:
            pygame.draw.rect(screen, SELECTED_TEXT_COLOR, ship_rect.inflate(24, 24), 3)

    hint = hint_font.render("Links/Rechts: wählen  Enter/Escape: zurück", True, TEXT_COLOR)
    hint_rect = hint.get_rect(center=(center_x, 500))
    screen.blit(hint, hint_rect)

    pygame.display.flip()


if __name__ == "__main__":
    main()
