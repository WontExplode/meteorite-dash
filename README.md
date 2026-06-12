# Meteorite Dash

Ein kleines 2D-Arcade-Spiel mit **PyGame-CE**. Du steuerst ein Raumschiff am
linken Bildschirmrand, weichst Meteoriten und Gegnern aus und sammelst dabei
immer mehr zurückgelegte Lichtjahre.

## Features

- Hauptmenü mit Schiffsauswahl
- vertikale Raumschiffsteuerung
- Standardwaffe mit 7 Schüssen und Munitions-Pickups
- zerstörbare Meteoriten und Gegner mit HP; Spieler-HP aus Schiffsrumpf
- Meteoriten in vier Größen mit zufälligen Farbvarianten
- Gegner mit unterschiedlichen Bewegungsmustern
- scrollendes Sternenfeld als Hintergrund
- Lightyears-Score als HUD-Anzeige
- Game-Over-Screen mit finalem Score
- dynamische Fenstergröße und Vollbild über einen gemeinsamen `Viewport`
- Menü-Musik, Game-Playlist und Game-Over-Sound

## Steuerung

- `Pfeil hoch` / `Pfeil runter`: Raumschiff bewegen oder Menüpunkt wechseln
- `Pfeil links` / `Pfeil rechts`: Raumschiff in der Schiffsauswahl wechseln
- `Space`: schießen (im Spiel)
- `R`: Waffe wechseln (im Spiel, wenn mehrere Waffen vorhanden)
- `Enter` / `Space`: Menüauswahl bestätigen
- `Escape`: im Spiel zurück ins Hauptmenü
- `F` / `F11`: Vollbild umschalten

## Entwicklung

```terminal
uv sync
uv run meteorite-dash
```

## Projektstruktur

```text
src/meteorite_dash/
  main.py              Entry-Point
  app.py               App-Loop und Szenenwechsel
  context.py           Geteilter Zustand, Resize und Vollbild
  viewport.py          Skalierung für dynamische Fenstergrößen
  config.py            Zentrale Konstanten
  assets.py            Asset-Pfade und Bild-Caching
  audio.py             Musik und Sounds
  score.py             Lightyears-Score
  entities.py          Gegner, Hindernisse und Munitions-Pickups
  projectiles.py       Spieler-Projektile
  weapons.py           Waffen-Loadout und Munitionslogik
  combat.py            Projektil- und Kollisionsschaden
  ships.py             Schiffsdatenblätter und Slot-Limits
  spawner.py           Timergesteuertes Spawning
  starfield.py         Bewegter Sternenhintergrund
  scenes/
    base.py            Basis-Szene mit gemeinsamer Loop
    main_menu.py       Hauptmenü
    ship_selection.py  Schiffsauswahl
    game.py            Spielszene
    death.py           Game-Over-Screen
```

## Checks

```terminal
uv run ruff format .
uv run ruff check .
uv run mypy
uv run pytest
```

Diese Checks laufen auch in der CI.

## Dev Setup

Pre-commit-Hook einrichten:

```terminal
git config core.hooksPath .githooks
```

## Hinweise

- Das Projekt nutzt `pygame-ce`, importiert im Code aber weiterhin `pygame`.
- Assets liegen unter `src/meteorite_dash/assets/`.
- Neue Positionen, Größen und Schriften sollten über `Viewport` skaliert werden,
  damit Resize und Vollbild funktionieren.
- Tests laufen headless mit Dummy-Video- und Dummy-Audiotreiber.
