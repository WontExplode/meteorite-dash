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
- sammelbare Münzen in Mustern (Linie, Welle, Bogen, Zickzack, Raute); Muster
  komplett eingesammelt gibt Bonus, eigener Münz-Score im HUD
- Shop: Münzen aus allen Läufen werden gespeichert und kaufen Schiffe,
  Zubehör (Schild, Magnet, Extra-Munition, Panzerung) und Schiffsfarben
- Zubehör wird pro Schiff in dessen Zubehörplätze gelegt und wirkt im Lauf
- Game-Over-Screen mit finalem Score
- dynamische Fenstergröße und Vollbild über einen gemeinsamen `Viewport`
- deterministische Simulation: fester Zeitschritt, Seed pro Lauf
  (`METEORITE_DASH_SEED` erzwingt einen), headless nachspielbar
- Menü-Musik, Game-Playlist, Game-Over-Sound und Schuss-Sound

## Steuerung

- `Pfeil hoch` / `Pfeil runter`: Raumschiff bewegen oder Menüpunkt wechseln
- `Pfeil links` / `Pfeil rechts`: Raumschiff in der Schiffsauswahl wechseln,
  Reiter im Shop wechseln
- `Enter` im Shop: kaufen, ausrüsten/ablegen oder Farbe wählen
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
  render.py            RenderContext: Referenzraum -> Fensterpixel beim Zeichnen
  config.py            Zentrale Konstanten
  assets.py            Asset-Pfade und Bild-Caching
  audio.py             Musik und Sounds
  score.py             Lightyears-Score
  simulation.py        Deterministischer Spielkern (fester Tick, Seed-Streams, Events)
  inputs.py            InputFrame: Eingaben als Bitmaske pro Tick
  difficulty.py        Director-Vertrag (DifficultyParams) für den Schwierigkeitsgrad
  headless.py          Simulation ohne Fenster abspielen (Tests, Replay-Prüfung)
  mathutil.py          Plattformstabiler Sinus/Abstand für die Simulation
  entities.py          Gegner, Hindernisse und Munitions-Pickups
  projectiles.py       Spieler-Projektile
  weapons.py           Waffen-Loadout und Munitionslogik
  combat.py            Projektil- und Kollisionsschaden
  ships.py             Schiffsdatenblätter, Slot-Limits, Preise und Farben
  accessories.py       Zubehör-Katalog (Schild, Magnet, Extra-Munition, Panzerung)
  progress.py          Guthaben, Freischaltungen, Ausrüstung (Shop-Regeln)
  persistence.py       JSON-Speicherstand im Nutzer-Datenverzeichnis
  coins.py             Münzen, Muster-Layouts und Formationen
  spawner.py           Timergesteuertes Spawning
  starfield.py         Bewegter Sternenhintergrund
  scenes/
    base.py            Basis-Szene mit gemeinsamer Loop
    main_menu.py       Hauptmenü
    ship_selection.py  Schiffsauswahl
    shop.py            Shop (Schiffe, Zubehör, Farben)
    widgets.py         Geteilte Zeichen-Helfer (Münz-Guthaben)
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
- Die Spiellogik rechnet im festen Referenzraum 800×600; erst beim Zeichnen
  skaliert der `RenderContext` auf das Fenster. Neue Positionen, Größen und
  Schriften gehen über `Viewport`/`RenderContext`, damit Resize und Vollbild
  funktionieren.
- Tests laufen headless mit Dummy-Video- und Dummy-Audiotreiber.
- Der Spielfortschritt liegt als `progress.json` im Nutzer-Datenverzeichnis
  (Linux: `~/.local/share/meteorite-dash/`, Windows: `%APPDATA%`, macOS:
  `~/Library/Application Support`). `METEORITE_DASH_SAVE_DIR` überschreibt
  den Ordner.
- `METEORITE_DASH_SEED=1234` startet jeden Lauf mit demselben Seed — gleiche
  Eingaben ergeben dann exakt dieselbe Runde.
