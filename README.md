# Meteorite Dash

Ein kleines 2D-Arcade-Spiel mit **PyGame-CE**. Du steuerst ein Raumschiff am
linken Bildschirmrand, weichst Meteoriten und Gegnern aus und sammelst dabei
immer mehr zurückgelegte Lichtjahre.

## Features

- Hauptmenü mit Start, Daily Run, Daily Bestenliste, Code eingeben,
  Schiffsauswahl und Shop
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
- Replays: jeder Lauf wird als `last.json` / `best.json` aufgezeichnet;
  `uv run meteorite-dash --verify datei.json` spielt ihn nach und prüft ihn
- Ghost: der beste gespeicherte Lauf zum selben Seed fliegt halbtransparent
  mit, das HUD zeigt den Vorsprung
- Daily Run: ein gemeinsamer Seed pro Tag für alle Spieler (ohne Server); der
  Tagesrekord fliegt als Ghost mit, der Game-Over-Screen zeigt den Vergleich
- Community-Läufe über Nostr: eigene Rekorde gehen signiert an öffentliche
  Relays, fremde Läufe zum Tages-Seed werden geholt, nachgespielt und
  fliegen als Ghost mit — kein eigener Server, kein Account
- Daily-Bestenliste: Top 5 zum Tages-Seed mit eigenem Rang, `R` lädt neu
- Lauf per Code weitergeben: `C` auf dem Game-Over-Screen veröffentlicht den
  Lauf unter drei Wörtern (z. B. `apfel berg wolke`); wer den Code im Menü
  eingibt, tritt gegen den Lauf an oder sieht ihn sich an
- Menü-Musik, Game-Playlist, Game-Over-Sound und Schuss-Sound

## Steuerung

- `Pfeil hoch` / `Pfeil runter`: Raumschiff bewegen oder Menüpunkt wechseln
- `Pfeil links` / `Pfeil rechts`: Raumschiff in der Schiffsauswahl wechseln,
  Reiter im Shop wechseln
- `Enter` im Shop: kaufen, ausrüsten/ablegen oder Farbe wählen
- `Space`: schießen (im Spiel)
- `R`: Waffe wechseln (im Spiel, wenn mehrere Waffen vorhanden)
- `Enter` / `Space`: Menüauswahl bestätigen
- `Tab` auf dem Game-Over-Screen nach einem Daily Run: Bestenliste
- `C` auf dem Game-Over-Screen: Lauf als Drei-Wort-Code teilen
- Menü „Code eingeben“: Code tippen, `Enter` = antreten, `Tab` = ansehen
- `R` in der Bestenliste: neu von den Relays laden
- `Escape`: im Spiel zurück ins Hauptmenü
- `F` / `F11`: Vollbild umschalten

## Entwicklung

```terminal
uv sync
uv run meteorite-dash
uv run meteorite-dash --verify replay.json    # Replay nachspielen und prüfen
uv run meteorite-dash --publish replay.json   # Replay an die Nostr-Relays senden
uv run meteorite-dash --fetch 579292414       # fremde Läufe zum Seed holen
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
  replay.py            Replay-Format, Recorder und Ablage (JSON)
  ghost.py             Ghost: Replay als zweite Simulation im Gleichschritt
  daily.py             Tages-Seed für den Daily Run
  sharecode.py         Kompaktes Binär-/Textformat eines Replays (Share-Code)
  identity.py          Nostr-Schlüssel pro Installation (identity.json)
  nostr.py             Nostr-Events und Relay-Client (websockets)
  exchange.py          Community-Läufe teilen, holen, prüfen, ablegen
  phrase.py            Drei-Wort-Phrase aus dem Lauf-Hash (assets/words_de.txt)
  leaderboard.py       Bestenliste aus gespeicherten Läufen (Logik)
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
    leaderboard.py     Daily-Bestenliste
    code_entry.py      Code eingeben, Lauf holen, antreten oder ansehen
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
  Eingaben ergeben dann exakt dieselbe Runde. Der Seed steht auch auf dem
  Game-Over-Screen.
- Replays liegen unter `replays/` neben `progress.json`. Eine Datei an
  Freunde schicken und `uv run meteorite-dash --verify datei.json` beweist den
  Lauf Tick für Tick. Liegt ein fremdes Replay im Ordner, erscheint es bei
  gleichem Seed (`METEORITE_DASH_SEED`) als Ghost.
- Der Daily-Seed hängt am UTC-Datum; der Tagesrekord liegt als
  `replays/daily-<datum>.json`.
- Community: beim ersten Start entsteht `identity.json` (zufälliger
  Nostr-Schlüssel, nur ein Pseudonym — Ordner kopieren nimmt ihn mit). Jeder
  eigene Rekord wird an die Relays aus `config.py` gesendet; das Hauptmenü
  zeigt, wie viele fremde Läufe es zum Tages-Seed gibt, der weiteste fliegt
  als Ghost mit (Game-Over-Screen: `REKORD … VON <pubkey>`). Fremde Läufe
  werden vor dem Import nachgespielt — was nicht bit-gleich nachspielt, wird
  verworfen. Mit `METEORITE_DASH_SEED=<seed>` holt auch ein freier Lauf die
  Läufe zu diesem Seed (Rennen gegen Freunde). `METEORITE_DASH_OFFLINE=1`
  schaltet Teilen und Holen ab. Öffentlich sichtbar sind Pubkey, Seed, Schiff,
  Zubehör, Eingaben und Endstand des Laufs — sonst nichts.
- Code weitergeben: Der Drei-Wort-Code ist aus dem Lauf berechnet (gleicher
  Lauf, gleicher Code) und eine Adresse, kein Passwort — der Lauf liegt
  öffentlich auf den Relays, 30 Tage lang. Wer den Code eingibt, bekommt den
  Lauf nur, wenn er bit-gleich nachspielt. Geholte Codes liegen als
  `replays/share-<wort>-<wort>-<wort>.json` und funktionieren danach auch
  offline.
