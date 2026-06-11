# CLAUDE.md

Leitfaden für Claude Code (und Menschen) in diesem Repository. Prosa ist
Deutsch — wie der restliche Code (Kommentare, UI-Texte, Issues). **Bezeichner,
Commits-in-Code, Strings und Fehlermeldungen bleiben exakt** wie im Quelltext.

---

## 1. Projekt

**Meteorite Dash** ist ein kleines 2D-Arcade-Spiel mit **PyGame-CE**. Man steuert
ein Raumschiff am linken Bildschirmrand und weicht von rechts heranfliegenden
Meteoriten und Gegnern aus.

Die Vision (Designvorlage):

- Raumschiff bewegt sich nach oben/unten.
- Meteoriten fliegen von rechts nach links; Geschwindigkeit steigt mit der Zeit.
- Sterne geben Punkte, wenn man sie einsammelt.
- Schießen mit **begrenzter Munition**; Munitions-Extras füllen sie wieder auf.
- Zerstörbare Meteoriten (große brauchen mehrere Treffer) und unzerstörbare, die
  man umfliegen muss.
- Kollision kostet ein Leben; bei null Leben ist das Spiel vorbei.
- Erweiterungen: Highscore, Sounds, Power-ups / Waffen-Upgrades (z. B. Minigun),
  feindliche Raumschiffe, Schiffsauswahl, Endbosse/Level.

> Ziel ist ein sauber strukturiertes, getestetes Spiel — nicht ein schneller
> Prototyp. Architektur und Tests stehen über Feature-Tempo.

---

## 2. Aktueller Stand (wichtig!)

Das Repo hat ein **solides Fundament** und einen spielbaren Kern-Loop. Vor dem
Implementieren neuer Features: prüfen, ob ein Baustein schon existiert.

**Vorhanden:**

- Szenen-Framework (`scenes/base.py`) mit Template-Method-Loop bei 60 FPS.
- Szenen: Hauptmenü, Schiffsauswahl, Spiel-Szene, Death-/Game-Over-Screen.
- `GameContext` als zentraler Zustands-/Ressourcen-Container.
- Dynamische Fenstergröße + Vollbild (`Viewport`, Referenz-Raum 800×600).
- Entities: `Meteorite`, `WaveEnemy` (Sinus-Bahn), `HunterEnemy` (verfolgt den
  Spieler vertikal). Gemeinsame Basis `Entity`.
- Meteoriten-Varianten in vier Größen (`Tiny`, `Small`, `Medium`, `Large`) mit
  je zwei zufällig gewählten Farb-Assets pro Instanz.
- Datengetriebener `Spawner` (gewichtete Tabelle, timergesteuert).
- Scrollendes Sternenfeld als Hintergrund (`StarField`).
- Musik (Menü-Loop + Spiel-Playlist), Soundeffekte, Asset-/Font-Caching.
- Spieler-Bewegung (vertikal) mit Trägheitsphysik, Kollision → Death-Screen.
- Schiffssystem (`ships.py`, Issue #11): `ShipSpec`-Datenblätter mit
  physikalischen Grundwerten (mass/thrust/hull, Slot-Zahlen) und abgeleiteten
  Spielwerten; 4 Schiffe mit Tint-Farbvarianten und Stat-Balken in der Auswahl.
- Lightyears-Score im HUD; finaler Score wird im Death-Screen angezeigt.
- Strikte Typprüfung, Linting, Tests, CI.

**Noch NICHT vorhanden** (aus dem Spec — meist als GitHub-Issue getrackt):

- **Schießen / Projektile** und **begrenzte Munition** sowie Munitions-Extras.
- **Sammelbare Sterne** für Punkte (`StarField` ist nur Deko, nicht einsammelbar).
- Leben-Zähler (aktuell beendet **eine** Kollision das Spiel).
- **Zerstörbare vs. unzerstörbare Meteoriten**, Trefferpunkte (HP), große
  Meteoriten mit mehreren Treffern.
- **Steigende Schwierigkeit** über die Zeit (Speed ist momentan konstant).
- Highscore-Persistenz, Power-ups/Waffen-Upgrades (Issue #12), Endbosse/Level
  (Issue #10), Münzen/Währung (Issue #14), Spieler-Stats (Issue #13),
  iOS/Android-Port (Issue #5). Waffen-/Zubehör-Slots sind in `ShipSpec` als
  Zahlen vorbereitet, aber noch ohne Funktion.

Issues sind die Feature-Quelle der Wahrheit: `gh issue list`.

---

## 3. Tech-Stack & Voraussetzungen

- **Python 3.13+** (`.python-version` → `3.13`).
- **pygame-ce ≥ 2.5.7** (Community-Edition, nicht das alte `pygame`).
- **uv** als Paket-/Umgebungs-Manager.
- Dev-Tools: **mypy** (strict), **ruff** (Format + Lint), **pytest**.

Installierte Pakete heißen im Import weiter `pygame` — Code importiert
`import pygame`, nie `pygame_ce`.

---

## 4. Befehle

```bash
uv sync                      # Umgebung + Abhängigkeiten einrichten
uv run meteorite-dash        # Spiel starten (Entry-Point aus pyproject.toml)

uv run ruff format .         # formatieren
uv run ruff check .          # linten
uv run mypy                  # Typprüfung (strict, über src + tests)
uv run pytest                # Tests
```

Pre-commit-Hook einmalig aktivieren (führt alle vier Checks vor jedem Commit aus):

```bash
git config core.hooksPath .githooks
```

**Alle vier Checks müssen grün sein**, bevor committet/gepusht wird — die CI
(`.github/workflows/ci.yml`) erzwingt dasselbe bei Push auf `main` und bei jedem
PR. `ruff format` läuft in CI als `--check` (kein Auto-Format), also lokal
formatieren.

---

## 5. Architektur

Datenfluss: `main.py` → `App` → aktive `Scene` → zurück über `Transition`.

```
main.main()                 Entry-Point, ruft App().run()
└─ App (app.py)             init pygame, baut GameContext, Szenen-Schleife
   ├─ GameContext           geteilter Zustand: screen, clock, fonts, music,
   │  (context.py)          assets, state, starfield, viewport; Resize/Vollbild
   └─ Scene (scenes/base)   Template-Method-Loop; gibt beim Verlassen ein
      ├─ MainMenu            Transition zurück → App wählt nächste Szene
      ├─ ShipSelection
      ├─ GameScene          eigentlicher Spiel-Loop (Spieler, Spawner, Entities)
      └─ DeathScene         Game-Over-Screen mit finalem Lightyears-Score
```

### Szenen & Transitions

- `Scene` (abstrakt) kapselt den 60-FPS-Loop: `tick → Events → update → draw`.
  Unterklassen implementieren **`handle_event`** und **`draw`**; optionale Hooks:
  `on_enter`, `on_exit`, `on_resize`, `update`.
- `Scene.run()` läuft bis `finish(transition)` gerufen wird, dann gibt es den
  `Transition` zurück. `App._create_scene` mappt `Transition` → nächste Szene.
- **Globale Events** behandelt die Basis-Szene zentral: `QUIT`, `VIDEORESIZE`
  (→ `context.apply_resize`), Vollbild-Toggle (`F` / `F11`). Szenen müssen das
  nicht selbst tun.
- Neue Szene hinzufügen: Unterklasse von `Scene`, neuen `Transition`-Wert
  ergänzen, in `App._create_scene` verdrahten.

### GameContext

Ein `@dataclass`, der alle geteilten Ressourcen hält und **Fenster-Resize +
Vollbild** besitzt (`apply_resize`, `toggle_fullscreen`). Beim Resize aktualisiert
er Screen, `Viewport` und `StarField` gemeinsam — Größenlogik lebt hier, nicht in
den Szenen. `GameState` hält den eigentlichen Spielzustand (aktuell
`selected_ship_index` und `final_light_years`); neue persistente Felder (Leben,
Munition, Highscore …) kommen hierher.

### Viewport — Referenz-Raum (zentrales Konzept)

Das Spiel wird in einem festen **Referenz-Raum 800×600** (`REFERENCE_SIZE`)
gedacht und vom `Viewport` auf das echte Fenster abgebildet:

- `px(x)` / `py(y)` — Position, pro Achse gestreckt (`scale_x` / `scale_y`),
  randlos (kein Letterbox).
- `s(value)` — Größen/Pixel-Längen, **einheitlich höhen-gebunden** (`scale`).
- `font(size)` / `font_size(size)` — höhen-gebundene, gecachte Schrift.
- Bei exakt 800×600 ist jeder Faktor `1.0` (Identität).

**Regel:** Jede neue Position/Größe/Schrift geht durch den `Viewport`. Niemals
rohe Fensterpixel hardcoden — sonst bricht Resize/Vollbild. Geschwindigkeiten und
Sprite-Größen sind höhen-gebunden, damit die vertikale Ausweich-Schwierigkeit
fenster-unabhängig bleibt.

### Entities & Spawner

- `Entity` (ABC): hält eine `pygame.Rect`-Hitbox, bewegt sich pro `update(dt,
  player_y)` nach links. Subklassen überschreiben `_update_vertical` (Standard:
  keine vertikale Bewegung) und `draw`.
- Bewegung ist **dt-basiert** (frame-rate-unabhängig) — float-Position intern,
  gerundet in `rect`. Beibehalten.
- Spawn über Fabrikfunktionen `spawn_meteorite` / `spawn_wave_enemy` /
  `spawn_hunter_enemy` mit Skalierungs-Parametern `sx` (Speed-x), `sy` (vertikale
  Bewegungs-Parameter) und `su` (Größe). Sie nehmen ein injiziertes
  `random.Random` → deterministisch testbar.
- Meteoriten-Größen und Bildvarianten liegen zentral in `METEORITE_VARIANTS`;
  neue Varianten dort ergänzen und weiter über `spawn_meteorite` erzeugen.
- `Spawner` zieht timergesteuert aus einer **gewichteten Tabelle** (`SpawnEntry`).
  Neuer Gegnertyp = neue `Entity`-Subklasse + `spawn_*`-Fabrik + Eintrag in
  `GameScene._spawn_table`.

### Assets & Audio

- `AssetLoader.load_ship` lädt/skaliert/rotiert Schiffsbilder aus dem
  ships-Ordner und tönt sie optional ein; `load_image` lädt generische Sprites
  wie Meteoriten. Beide Wege **cachen** nach `(path, size, rotate_left, tint)`.
  Bilder/Schriften nie pro Frame laden.
- Pfade nur über `image_path` / `sound_path` (relativ zum Paket).
- `MusicPlayer` kapselt `pygame.mixer.music`; die Spiel-Playlist nutzt das
  `GAME_MUSIC_ENDED`-Userevent, um Tracks weiterzuschalten.

### Score / Lightyears

- `DistanceScore` in `score.py` zählt die zurückgelegte Strecke in Lightyears
  dt-basiert hoch.
- `rate_multiplier` ist der Erweiterungspunkt für spätere Speed-Phasen,
  Meilensteine oder Boss-Abschnitte.
- `GameScene` rendert den Score als transparentes HUD (`LIGHTYRS ...`) über den
  `Viewport` und schreibt bei Kollision `state.final_light_years`.
- `DeathScene` liest `state.final_light_years` und zeigt den finalen Wert auf dem
  Game-Over-Screen.

---

## 6. Konventionen & Best Practices

1. **Typisierung ist strikt.** `mypy --strict` muss durchlaufen. Keine
   ungetypten Funktionen, kein loses `Any`. Public-APIs voll annotiert.
2. **Ruff entscheidet Stil.** `line-length = 100`. Aktive Regelgruppen siehe
   `pyproject.toml` (F, E, W, I, N, UP, B, SIM, RUF). Vor dem Commit
   `ruff format .` ausführen.
3. **Konstanten zentral in `config.py`.** Spielwerte (Speeds, Größen, Farben,
   Gewichte, Fenstergröße) gehören dorthin — eine Quelle der Wahrheit, keine
   magischen Zahlen in der Logik.
4. **Alles über den Viewport** rendern/platzieren (siehe §5). Resize/Vollbild
   müssen weiter funktionieren.
5. **Determinismus für Testbarkeit.** Zufall immer über ein injiziertes
   `random.Random`. Reine Spiel-Logik (Bewegung, Kollision, Spawn) ohne harte
   Display-Abhängigkeit halten, damit sie headless testbar bleibt.
6. **dt-basierte Bewegung** beibehalten — nichts an feste FPS koppeln.
7. **Kleine, fokussierte Module.** Dem bestehenden Schnitt folgen (eine
   Verantwortung pro Datei). Render-Code von reiner Logik trennen.
8. **Sprache:** Prosa/Kommentare/UI auf Deutsch, **Bezeichner auf Englisch** —
   wie im bestehenden Code.
9. **Dokumentation aktuell halten.** Bei jeder Änderung prüfen, ob `CLAUDE.md`
   und/oder `README.md` angepasst werden müssen. Architektur-, Workflow- und
   Projektstand-Änderungen gehören in `CLAUDE.md`; nutzer- oder
   entwicklerrelevante Projektbeschreibung in `README.md`.
10. **Issues sind der Plan.** Features gegen das passende GitHub-Issue bauen; bei
   neuem Feature ggf. Issue verlinken/ergänzen.

### Neues Feature — typische Schritte

- **Gegner/Hindernis:** `Entity`-Subklasse → `spawn_*`-Fabrik (mit `sx/sy/su`) →
  Gewicht in `GameScene._spawn_table` → Logik-Test mit gesetztem Seed.
- **Szene/Screen** (z. B. Game-Over, Issue #15): `Scene`-Subklasse +
  `Transition` + Verdrahtung in `App._create_scene`.
- **Spielzustand** (Leben/Munition/Highscore): Felder in `GameState`, in
  `GameScene` fortschreiben, über `Viewport`-Schrift im HUD rendern.

---

## 7. Tests

- Framework: **pytest**, Tests unter `tests/`.
- **Headless:** `tests/conftest.py` setzt `SDL_VIDEODRIVER=dummy` und
  `SDL_AUDIODRIVER=dummy` (per `setdefault`, vor dem ersten `pygame`-Import), damit
  Tests ohne Display/Audio laufen. In CI sind dieselben Variablen für den
  pytest-Schritt gesetzt. Bei neuem display-/audio-berührendem Test denselben
  Weg nutzen.
- Muster: `FakeKeys` für Tastatur, gesetzter RNG-Seed, `context`-Fixture baut
  einen vollständigen `GameContext`. Logik (`test_logic.py`) und Skalierung/Resize
  (`test_viewport.py`) sind getrennt.
- Neue Spiel-Logik braucht einen Test. Reine Funktionen bevorzugen, die ohne
  laufenden Loop prüfbar sind (siehe vorhandene Spawner-/Entity-/Player-Tests).

---

## 8. Security

Das Spiel ist offline, single-player, ohne Netzwerk, Accounts oder Secrets im
Spielcode. Die realistischen Punkte:

- **Keine Secrets ins Repo.** `.env*` ist in `.gitignore`. Der
  `CLAUDE_CODE_OAUTH_TOKEN` lebt nur als **GitHub-Actions-Secret** — niemals
  loggen, ausgeben oder committen.
- **GitHub-Actions-Automation:** `claude.yml` reagiert auf `@claude`-Mentions,
  `claude-code-review.yml` reviewt PRs. Workflow-Permissions minimal halten
  (Prinzip der geringsten Rechte); `pull-requests: write` in der Review-Action ist
  bewusst nötig, mehr nicht hinzufügen.
- **Asset-Laden:** Bilder/Sounds nur aus dem Paketverzeichnis über
  `image_path`/`sound_path`. Werden später **nutzergelieferte Dateien** geladen
  (Skins, Mods), Pfade validieren (kein Path-Traversal außerhalb eines erlaubten
  Verzeichnisses) und nur erwartete Dateitypen akzeptieren.
- **Persistenz (Highscore/Settings, geplant):** **JSON, niemals `pickle`/`eval`**
  auf nicht vertrauenswürdige Daten. Beim Einlesen defensiv parsen (fehlende/
  falsch typisierte Felder abfangen), in ein nutzer-beschreibbares Verzeichnis
  schreiben, kaputte Dateien tolerieren statt crashen.
- **Abhängigkeiten:** über `uv` gepinnt halten; nur etablierte Pakete (pygame-ce)
  aus PyPI. Keine ungeprüften Downloads zur Laufzeit.

Es gibt hier **keine** echten Angriffsflächen wie Eingabe-Eval, Deserialisierung
oder Netzwerk — keine erfinden. Defensiv werden, sobald Persistenz oder
nutzergelieferte Inhalte dazukommen.

---

## 9. Gotchas

- **pygame-ce, nicht pygame** — Import bleibt `pygame`, aber Abhängigkeit ist
  `pygame-ce`. Nicht das alte `pygame` installieren.
- **`SysFont("arial", …)`** ist systemabhängig; Issue #5 nennt das Bündeln einer
  `.ttf` für Portabilität (z. B. Mobile). Bis dahin keine Schrift-Annahmen treffen.
- **`.mp3`-Musik** ist nicht überall ideal (Issue #5 nennt `.ogg` für Mobile).
- **Vollbild** merkt sich die Fenstergröße (`_windowed_size`); OS-`VIDEORESIZE`
  wird im Vollbild ignoriert. Resize-Logik nur in `GameContext` ändern, beide
  Pfade (windowed/fullscreen) bedenken.
- **Kollision = sofort Death-Screen.** Es gibt noch keine Leben. Wer Leben
  einbaut, ersetzt den direkten `finish(Transition.DEATH_SCREEN)`-Pfad in
  `GameScene.update`.
- **`Player.update` clampt nur Bewegung**, holt das Schiff aber nicht aus dem Bild
  zurück — `GameScene.on_resize` re-klemmt es nach einem Resize aktiv.
