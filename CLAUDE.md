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
- Schießen mit **begrenzter Munition**; Munitions-Extras füllen die Standardwaffe wieder auf.
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
- Szenen: Hauptmenü (Start, Daily Run, Schiffsauswahl, Shop), Spiel-Szene,
  Death-/Game-Over-Screen.
- `GameContext` als zentraler Zustands-/Ressourcen-Container.
- Dynamische Fenstergröße + Vollbild (`Viewport`, Referenz-Raum 800×600). Die
  Spiellogik rechnet **nur** im Referenzraum; `RenderContext` (`render.py`)
  übersetzt beim Zeichnen ins Fenster.
- Entities: `Meteorite`, `WaveEnemy` (Sinus-Bahn), `HunterEnemy` (verfolgt den
  Spieler vertikal). Gemeinsame Basis `Entity`.
- Meteoriten-Varianten in vier Größen (`Tiny`, `Small`, `Medium`, `Large`) mit
  je zwei zufällig gewählten Farb-Assets pro Instanz.
- Datengetriebener `Spawner` (gewichtete Tabelle, timergesteuert).
- Scrollendes Sternenfeld als Hintergrund (`StarField`).
- Musik (Menü-Loop + Spiel-Playlist), Soundeffekte, Asset-/Font-Caching.
- Spieler-Bewegung (vertikal) mit Trägheitsphysik; Kollisionsschaden und Tod bei 0 HP.
- **Waffensystem:** Standard-Schuss (7 Munition, startet voll), Projektile,
  Munitions-Pickups im Spawner, Waffen-HUD; `WeaponLoadout` respektiert
  `ShipSpec.weapon_slots` und ist für Spezialwaffen + `R`-Wechsel vorbereitet.
- **Kampf / HP:** Spieler-HP aus `ShipSpec.hull`; zerstörbare Meteoriten und
  Gegner mit größenabhängigen HP; Projektil- und Kollisionsschaden über
  `combat.py`.
- Schiffssystem (`ships.py`, Issue #11): `ShipSpec`-Datenblätter mit
  physikalischen Grundwerten (mass/thrust/hull, Slot-Zahlen) und abgeleiteten
  Spielwerten; 4 Schiffe mit Tint-Farbvarianten und Stat-Balken in der Auswahl.
- Lightyears-Score im HUD; finaler Score wird im Death-Screen angezeigt.
- Münzen (`coins.py`, Issue #14): sammelbare Münz-Muster (`line`, `wave`,
  `arc`, `zigzag`, `diamond`) als `CoinFormation`; komplett eingesammeltes
  Muster zahlt Bonus. Eigener Münz-Score im HUD und Death-Screen; nach jedem
  Lauf wandern die Münzen ins persistente Guthaben.
- **Shop & Fortschritt** (Issue #14): `Progress` (Guthaben, Freischaltungen,
  Ausrüstung) wird als JSON im Nutzer-Datenverzeichnis gespeichert
  (`persistence.py`). `ShopScene` mit drei Reitern: Schiffe freischalten
  (`ShipSpec.price`), Zubehör für die `accessory_slots` (Schild, Magnet,
  Extra-Munition, Panzerung — `accessories.py`) und Farbvarianten (`TINTS` in
  `ships.py`). Schiffsauswahl zeigt gesperrte Schiffe abgedunkelt mit Preis.
- **Deterministische Simulation** (Issue #34): `Simulation` (`simulation.py`)
  tickt mit festem `SIM_DT`, Zufall aus Seed-Streams, Eingaben als
  `InputFrame`; jede Interaktion liefert ein `SimEvent` mit Snapshot
  (HP/Munition/Score/Münzen). `headless.run` spielt Eingabefolgen ohne Fenster
  ab, `state_hash()` beweist Gleichheit. Director-Vertrag (`difficulty.py`) für
  #32/#33 steht.
- **Adaptiver Director-Regelkern** (Issue #33): `AdaptiveDirector`
  (`adaptive_difficulty.py`) schätzt aus sicheren Passagen, schadensfreier Zeit,
  Schaden, Near Misses, HP und Munition eine individuelle Belastungsgrenze.
  Sein vollständiger Zustand fließt über `state_key()` in den Simulationshash.
  `mode_directors.py` liefert für Free eine frische adaptive, für Daily weiterhin
  eine konstante Instanz. Replays speichern Director-Art und getrennte
  Regelversion, sodass Headless-Prüfungen dieselbe Strategie rekonstruieren.
- **Replays** (Issue #34): `Recorder` zeichnet jeden Lauf als `Replay`
  (`RunConfig` + Eingaben, RLE) auf; nach dem Tod landet er als `last.json` /
  `best.json` im `ReplayStore`. `headless.verify` spielt ein Replay nach und
  vergleicht Endzustand + Hash; `uv run meteorite-dash --verify datei.json`
  macht das von der Kommandozeile. Golden-Regressionstest in
  `tests/test_replay.py` mit `tests/replays/golden-*.json`.
- **Ghost** (Issue #34): Im Daily spielt `ghost.py` den kompatiblen Tagesrekord
  als zweite `Simulation` im Gleichschritt nach; `GameScene` zeichnet nur sein
  Schiff halbtransparent und zeigt `GHOST <ly> ±Δ` im HUD. Der adaptive Free
  Mode lädt bewusst keinen Ghost.
- **Daily Run** (Issue #34): Menüpunkt mit gemeinsamem Tages-Seed
  (`daily.py`, SHA-256 aus Salt + UTC-Datum, kein Server). Rekord des Tages
  als `daily-<datum>.json`, fliegt als Ghost mit; Death-Screen zeigt Modus,
  Rekordvergleich und Seed.
- **Community-Läufe über Nostr** (Issue #34 „+ Server funktion“, ohne eigenen
  Server): jeder eigene Rekord geht als signiertes, ersetzbares Event
  (`kind:30078`, `d = meteorite-dash:<SIM_VERSION>:<seed>`) an öffentliche
  Relays (`nostr.py`, `exchange.py`); Inhalt ist der kompakte Share-Code
  (`sharecode.py`). Das Menü holt die Läufe zum Tages-Seed im Voraus, spielt
  jeden mit `headless.verify` nach und legt bestandene als
  `nostr-<seed>-<pubkey8>.json` in den `ReplayStore` → der weiteste fliegt als
  Ghost mit. Identität = zufälliger Schlüssel in `identity.json`
  (`identity.py`). `METEORITE_DASH_OFFLINE=1` schaltet alles ab.
- **Daily-Bestenliste** (`leaderboard.py`, `scenes/leaderboard.py`): Top 5
  zum Tages-Seed aus dem `ReplayStore` (bester Lauf je Spieler, „DU“ für
  eigene), eigener Rang darunter, `R` holt neu von den Relays. Menüpunkt
  „Daily Bestenliste“, nach einem Daily Run auch per `Tab` vom Death-Screen.
- **Lauf per Code weitergeben** (`phrase.py`, `scenes/code_entry.py`): Death-Screen
  `C` veröffentlicht den Lauf unter einer Drei-Wort-Phrase (aus dem
  `state_hash`, deutsche Wortliste `assets/words_de.txt`, 2048³ Kombinationen),
  Menüpunkt „Code eingeben“ holt ihn, prüft ihn und bietet „antreten“
  (Ghost) oder „ansehen“ (Zuschauer-Modus der `GameScene`).
- Strikte Typprüfung, Linting, Tests, CI.

**Noch NICHT vorhanden** (aus dem Spec — meist als GitHub-Issue getrackt):

- **Sammelbare Sterne** für Punkte (`StarField` ist nur Deko, nicht einsammelbar).
- **Spezialwaffen-Pickups** (Loadout und Slot-Limit sind vorbereitet).
- **Unzerstörbare Meteoriten** (zerstörbare Varianten mit HP sind implementiert).
- **Steigende Schwierigkeit** über die Zeit (Vertrag in `difficulty.py`,
  Umsetzung Issues #32/#33 — nicht Teil von #34).
- Freunde-Filter nach Pubkey in der Bestenliste; QR-Anzeige des Share-Codes
  (Format steht in `sharecode.py`).
- **Produktive Schwierigkeitssteuerung:** Der adaptive Regelkern ist vorhanden,
  wird aber noch nicht in den Free Mode injiziert. Die feste Daily-Zeitrampe
  bleibt eine getrennte Aufgabe des zweiten Modus.
- **Weitere adaptive Stellgrößen und Diagnose-HUD:** Free nutzt bereits Speed-
  und Spawnintervallfaktor. Gegnermix, Größenbias und das geplante verborgene
  Debug-HUD sind noch nicht umgesetzt; die feste Daily-Zeitrampe bleibt eine
  getrennte Aufgabe des zweiten Modus.
- Server-Anbindung für Daily-Bestenlisten (Issue #34 „+ Server funktion“):
  Replay-Datei ist die Upload-Einheit, `headless.verify` die Prüfung.
- Highscore-Persistenz, Power-ups/Waffen-Upgrades (Issue #12), Endbosse/Level
  (Issue #10), Spieler-Stats (Issue #13), iOS/Android-Port (Issue #5).

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
uv run meteorite-dash --verify replay.json   # Replay headless nachspielen, Trace + PASS/FAIL
uv run meteorite-dash --publish replay.json  # Replay als eigenen Bestlauf an die Relays senden
uv run meteorite-dash --fetch 579292414      # fremde Läufe zum Seed holen, prüfen, ablegen

uv run ruff format .         # formatieren
uv run ruff check .          # linten
uv run mypy                  # Typprüfung (strict, über src + tests)
uv run pytest                # Tests
uv run interrogate           # Docstring-Abdeckung (fail-under in pyproject.toml)
```

Pre-commit-Hook einmalig aktivieren (führt alle fünf Checks vor jedem Commit aus):

```bash
git config core.hooksPath .githooks
```

**Alle fünf Checks müssen grün sein**, bevor committet/gepusht wird — die CI
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
      ├─ ShopScene          Münzen gegen Schiffe, Zubehör, Farben
      ├─ LeaderboardScene   Daily-Bestenliste aus dem ReplayStore
      ├─ CodeEntryScene     Drei-Wort-Code tippen -> Lauf holen -> Rennen/Ansehen
      ├─ GameScene          Fixstep-Loop um `Simulation` (simulation.py) + Rendering
      └─ DeathScene         Game-Over-Screen mit finalem Lightyears-Score
```

### Szenen & Transitions

- `Scene` (abstrakt) kapselt den 60-FPS-Loop: `tick → Events → update → draw`.
  Unterklassen implementieren **`handle_event`** und **`draw`**; optionale Hooks:
  `on_enter`, `on_exit`, `on_resize`, `update`.
- `Scene.run()` läuft bis `finish(transition)` gerufen wird, dann gibt es den
  `Transition` zurück. `App._create_scene` mappt `Transition` → nächste Szene.
- **Globale Events** behandelt die Basis-Szene zentral in `dispatch`: `QUIT`,
  `VIDEORESIZE` (→ `context.apply_resize`), Vollbild-Toggle (`F` / `F11`).
  Szenen müssen das nicht selbst tun. Szenen mit Texteingabe setzen
  `captures_text = True` — dann ist `F` ein Buchstabe, nur `F11` bleibt global.
- Neue Szene hinzufügen: Unterklasse von `Scene`, neuen `Transition`-Wert
  ergänzen, in `App._create_scene` verdrahten.

### GameContext

Ein `@dataclass`, der alle geteilten Ressourcen hält und **Fenster-Resize +
Vollbild** besitzt (`apply_resize`, `toggle_fullscreen`). Beim Resize aktualisiert
er Screen, `Viewport` und `StarField` gemeinsam — Größenlogik lebt hier, nicht in
den Szenen. `GameState` hält den eigentlichen Spielzustand (aktuell
`selected_ship_index`, `final_light_years`, `final_coins` und den persistenten
`progress`); neue Session-Felder (Leben, Munition …) kommen hierher, alles, was
über den Neustart hinaus gelten soll, in `Progress`. `GameContext.store`
(`SaveStore | None`) schreibt den Fortschritt; `save_progress()` ist ohne Store
(Tests) ein No-op. `GameContext.exchange` (`RunExchange | None`) ist der
Nostr-Anschluss — `None` in Tests und bei `METEORITE_DASH_OFFLINE`.

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

**Simulation vs. Rendering:** Spieler, Entities, Projektile und Münzen rechnen
**ausschließlich im Referenzraum** — Hitboxen, Geschwindigkeiten, Spawn-Fläche
(`REFERENCE_SIZE`). Die Fenstergröße erreicht die Logik nie. Beim Zeichnen bekommt
jedes Objekt einen `RenderContext` (`render.py`: Surface, Viewport, optionaler
`AssetLoader`); `ctx.rect(ref_rect)` liefert das Fenster-Rechteck, `ctx.image`
das Sprite in genau dieser Größe aus dem Cache. Resize/Vollbild ändern damit nur
das Bild, nie den Spielzustand — Grundlage für Determinismus und Replays.

### Simulation & Determinismus (Issue #34)

- `simulation.py`: `Simulation(RunConfig)` ist der komplette Lauf-Zustand —
  Spieler, Loadout, Zubehör-Effekte, Spawner, Entities, Münzen, Projektile,
  Score. `step(inputs: InputFrame)` rückt genau einen festen Tick `SIM_DT`
  (`config.py`) vor; nach `DEATH` ist `step` ein No-op. Die Klasse kennt weder
  Fenster, Wandzeit noch Tastatur.
- **Seed-Streams:** `seeded(seed, "spawn" | "coins" | "director")` liefert je
  Konsument einen eigenen `random.Random`. Neue Zufallsquelle = neuer Stream,
  nie einen bestehenden mitbenutzen (sonst verschieben sich fremde Würfe).
  `RunConfig(seed, ship, accessories)` beschreibt alles außer den Eingaben;
  `pick_seed()` würfelt 32 Bit oder liest `METEORITE_DASH_SEED`.
- **Eingaben:** `inputs.InputFrame` (IntFlag `UP | DOWN | FIRE | SWAP_WEAPON`).
  `GameScene` baut pro Tick `from_pressed(keys) | pending` — `SWAP_WEAPON` ist
  eine Flanke aus `KEYDOWN` und gilt genau einen Tick.
- **Fester Zeitschritt:** `GameScene.update(dt)` akkumuliert Wandzeit und ruft
  `step` bis zu `MAX_STEPS_PER_FRAME`-mal; Rest verfällt. Sternenfeld und
  HUD-Fades laufen weiter mit Wandzeit — sie sind Deko.
- **Events & Beweis:** jede Interaktion (`EventKind`: FIRED, HIT, DESTROYED,
  AMMO_PICKUP, COIN, COIN_BONUS, SHIELD, CONTACT, DEATH) liefert ein `SimEvent`
  mit `Snapshot(tick, hp, ammo, light_years, coins, shield)` **direkt nach**
  der Interaktion plus `value` (Schaden/Münzen/Bonus). `GameScene` reagiert nur
  darauf (Sound, Bonus-Hinweis, Death-Screen). `headless.run(config, inputs)`
  spielt eine Eingabefolge ohne Display ab und liefert einen `Trace`;
  `scripted_inputs(seed, ticks)` erzeugt reproduzierbare Pseudo-Eingaben.
- **Hash:** `Simulation.state_hash()` = SHA-256 über `state_key()` — jedes
  Objekt liefert seinen Zustand kanonisch (Floats als `.hex()`, RNG-Zustände
  inklusive). Neues Zustandsfeld → in `state_key` aufnehmen.
- **Plattformstabil:** im Sim-Pfad `mathutil.det_sin` / `det_hypot` statt
  `math.sin` / `math.hypot` (libm darf im letzten Bit abweichen; Polynom und
  `sqrt` nicht). Render-Code darf `math` weiter nutzen.
- **`SIM_VERSION`** (`config.py`) bei jeder Regel-/Physik-/Spawn-Änderung
  erhöhen; Replays tragen die Version.

### Director-Vertrag (Issues #32/#33)

`difficulty.py` legt fest, wie ein Schwierigkeits-Director andocken darf, ohne
Replays zu brechen:

- `Director.params(sim: SimulationView, rng) -> DifficultyParams` wird **jeden
  Tick** aus `Simulation.step` gerufen; `rng` ist der Stream `<seed>:director`.
  Kadenz zählt der Director über `sim.tick`, nie über Sekunden.
- `DifficultyParams(speed_multiplier, spawn_interval_multiplier)`: die
  Simulation wendet sie auf `Entity.update(..., speed_scale)` bzw.
  `Spawner.update(..., interval_scale=)` an. Neue Stellgröße = neues Feld hier
  + Anwendung in `step`.
- Erlaubte Eingaben: alles aus `SimulationView` (Tick, Spieler, Loadout,
  Entities, Münzen, Lightyears) und `rng`. Verboten: Wandzeit, FPS, Fenster,
  `random` ohne Seed. Zustandsbehaftete Implementierungen liefern zusätzlich
  einen kanonischen `StatefulDirector.state_key()`; `Simulation.state_key()`
  nimmt ihn in den Hash auf. Zustandslose Directors verändern bestehende Hashes
  dadurch nicht.
- `ConstantDirector` bleibt der unveränderte Daily-Standard; der adaptive Free-
  Teil wird über `Simulation(director=…)` injiziert.
- `AdaptiveDirector` lebt bewusst separat in `adaptive_difficulty.py`: sichere
  Passagen und schadensfreies Spielen erhöhen `mastery`; Schaden und gehäufte
  Near Misses erhöhen `stress`. Die Intensität steigt geglättet und fällt
  schneller, mit Start-Schonzeit, Damage-Hold und Low-HP-Cap. Seine Parameter
  stehen als `DIFFICULTY_*`-Konstanten in `config.py`.
- `mode_directors.py` ist die einzige Modusgrenze: Free wird auf
  `DirectorKind.ADAPTIVE`, Daily auf `DirectorKind.CONSTANT` abgebildet.
  Factory und getrennte Regelversionen werden von `GameScene`, Ghost und
  Headless-Replay gemeinsam genutzt. Änderungen nur am Tuning erhöhen die
  betreffende Director-Version, nicht die gemeinsame `SIM_VERSION`.

### Replays (Issue #34)

- `replay.py`: `Replay` = `RunConfig` + `frames` (Lauflängen `(Maske, Ticks)`)
  + `final: Snapshot` + `state_hash` + `sim_version`/`recorded_at`/`mode`/
  `label` + `director_kind`/`director_version`. `inputs()` expandiert die Frames
  wieder zu `InputFrame`s. Alte Dateien ohne Director-Felder werden als
  bisherige konstante Strategie gelesen.
- JSON-Format wie der Speicherstand: `to_dict` / `from_dict` (defensiv,
  `None` statt Exception bei falschen Typen, unbekannten Katalog-IDs,
  ungültigen Frames, `bool`-als-`int`). `REPLAY_FORMAT_VERSION` in `config.py`.
- `Recorder(config)`: `record(inputs)` pro Tick **vor** `sim.step`, `finish(sim)`
  liefert das `Replay` mit Snapshot und Hash. `GameScene.step` zeichnet nur
  auf, solange `sim.is_over` False ist; Abbruch per Escape speichert nichts.
- `ReplayStore(dir)` (`GameContext.replays`, in Tests `None`): `save`/`load`
  per Name (`path_for` bereinigt auf `[A-Za-z0-9_-]`, kein Path-Traversal),
  `all()`, `best_for_seed(seed, ...)` mit Filtern für Simulationsversion, Modus,
  Director-Art und -Version. Ablage:
  `default_replay_dir()` = Speicherordner + `replays/`. `GameScene._store_replay`
  schreibt beim `DEATH`-Event `last` immer und `best` bei neuer Bestweite;
  `GameState.last_replay` und `final_seed` tragen den Lauf zum Death-Screen.
- **Prüfen:** `headless.run_replay(replay)` rekonstruiert ohne expliziten
  Override die aufgezeichnete Director-Art. `headless.verify(replay)` →
  `Verification(ok, version_matches)` — `ok` heißt: passende Simulations- und
  Director-Version, gleicher `Snapshot`, gleicher Hash. `format_trace` druckt eine Zeile pro
  Interaktion. CLI: `meteorite-dash --verify datei.json` (Exit 0/1). Das ist
  auch die spätere Server-Prüfung eingereichter Läufe.
- **Golden-Regression:** `tests/replays/golden-<x>.json` (Replays aus
  `scripted_inputs`, `GOLDEN_RUNS` in `test_replay.py`) + `golden-<x>.trace.json`
  (Event-Zeilen). Der Test prüft
  `verify(...).ok` und vergleicht jede Zeile — wörtlich „Score/HP/Munition
  stimmen nach jeder Interaktion“. Nach bewusster Regeländerung:
  `SIM_VERSION` erhöhen und `UPDATE_GOLDEN=1 uv run pytest tests/test_replay.py
  -k golden`.

### Ghost (Issue #34)

- `ghost.py`: `Ghost(replay)` = eigene `Simulation(replay.config)` mit der im
  Replay gespeicherten Director-Art + Iterator über `replay.inputs()`. `step()`
  pro Tick, `finished` wenn Eingaben
  aufgebraucht oder tot, danach `consistent` (Snapshot + Hash == Aufzeichnung)
  — jeder Ghost-Lauf ist damit ein Determinismus-Test im Spiel. `delta(ly)` =
  Vorsprung des Spielers.
- Bewusst **Re-Simulation statt Positionsliste**: Datei bleibt klein, Ghost-
  Score läuft live mit. Die Ghost-Welt divergiert nach der ersten Abweichung
  (Hunter, Treffer, Münzen) — deshalb wird nur das Schiff gezeichnet.
- `GameScene(context, seed=…, ghost=…)`: Nur im Daily sucht `find_ghost` nach
  gleichem Seed, Modus, Director und Version. Free ignoriert auch explizit
  übergebene Ghosts. `step()` rückt
  Ghost und Spieler gemeinsam vor; der Ghost fasst die Spieler-Simulation nie
  an. Zeichnen: `ghost_image(size)` = getöntes Schiff (`GHOST_TINT`) mit
  `GHOST_ALPHA`, pro Größe gecacht; Ghost hinter dem Spieler, verschwindet mit
  `finished`. HUD `GHOST <ly> ±Δ` über `GHOST_HUD_TOP_RIGHT`.
- Daily-Ghost gegen Freunde: Ein kompatibles Daily-Replay kann in den
  `replays/`-Ordner gelegt werden; Free-Replays bleiben reine Aufzeichnungen
  und Prüfartefakte.

### Daily Run (Issue #34)

- `daily.py`: `daily_seed(day)` = SHA-256 über `DAILY_SEED_SALT:<ISO-Datum>`,
  auf `SEED_BITS` gekürzt; `today_utc()` liefert den UTC-Tag (Tageswechsel für
  alle gleichzeitig). `daily_replay_name(day)` → `daily-<datum>`. Werte sind
  in `tests/test_daily.py` festgenagelt — Salt/Formel ändern heißt neue Serie.
- `RunMode` (`replay.py`): `FREE` | `DAILY`, im Replay gespeichert (`mode`,
  `label` = Datum). `Transition.START_DAILY` → `App._create_scene` baut
  `GameScene(seed=daily_seed(today), mode=DAILY, label=datum)`; Menüpunkt
  „Daily Run“ in `MENU_ITEMS` (`MENU_ITEM_SPACING` hält fünf Einträge im Bild).
- Rekord: `GameScene.record_name()` — `best` im freien Lauf, `daily-<datum>`
  im Daily; `_store_replay` überschreibt nur bei größerer Lichtjahr-Zahl.
  Ghost = kompatibles `best_for_seed(daily_seed, mode=DAILY, ...)`, also
  automatisch der Tagesrekord und niemals ein Free-Replay mit gleichem Seed.
- Death-Screen: `GameState.final_mode`/`final_label` (Zeile „DAILY RUN <datum>“),
  `final_record_light_years` (Rekord des Ghosts vor diesem Lauf) →
  `DeathScene._record_line`: „NEUER REKORD (VORHER …)“ oder „REKORD … (±Δ)“,
  dazu `SEED …`.
- Fairness-Entscheidung: Schiff und Zubehör sind frei (stehen im Replay-Header);
  Vergleich ist lokal. Gleicher Seed heißt gleiche Regeln und gleicher Start —
  die Spawn-Folge divergiert nach der ersten Spieler-Abweichung (Hunter,
  Treffer, Münzen), das ist gewollt.

### Community-Läufe über Nostr (Issue #34)

Läufe austauschen ohne eigenen Server: öffentliche Nostr-Relays sind der
Briefkasten, die Simulation ist der Richter.

- `sharecode.py`: `encode`/`decode` packen ein `Replay` in Bytes (Header,
  Snapshot, Hash, ein Byte pro Eingabe-Event, CRC-32), `to_text`/`from_text`
  als Base64url. ~3,5 Byte pro Spielsekunde; `decode` ist defensiv wie
  `Replay.from_dict`. Das ist das Wire-Format — auch für späteres QR/Tippen.
  Format-Änderung → `SHARECODE_VERSION` erhöhen.
- `identity.py`: `Identity` = 32 Byte Zufall (`secrets`), Pubkey x-only,
  BIP-340-Schnorr über `coincurve`. `IdentityStore` speichert
  `identity.json` neben `progress.json` (0600, atomar); fehlend/kaputt →
  neuer Schlüssel. Der Schlüssel ist nur ein Pseudonym.
- `nostr.py`: NIP-01-Events (`event_id` = SHA-256 der kanonischen Liste,
  `build_run_event`, `parse_run_event` prüft Form, ID, Signatur, Share-Code
  und dass der `d`-Tag zum Inhalt passt). `RelayClient` (`websockets`)
  spricht alle `NOSTR_RELAYS` parallel, je Verbindung `NOSTR_TIMEOUT`;
  `publish` zählt `OK true`, `fetch` sammelt bis `EOSE` und dedupliziert.
  Jeder Netzfehler wird geloggt und zählt als „Relay nicht erreichbar“ —
  nie eine Exception nach außen.
- `exchange.py`: `RunExchange(identity, store)` ist der Trichter.
  `import_runs(seed)`: holen → `parse_run_event` → eigene überspringen →
  `SIM_VERSION`/Seed/`NOSTR_MAX_TICKS` prüfen → weiteste zuerst
  `headless.verify` → `store.save(nostr-<seed>-<pubkey8>, author=pubkey)`.
  Schon vorhandene (gleicher Hash) werden nicht erneut nachgespielt.
  `prefetch(seed)` läuft im Thread, `wait_for(seed, timeout)` joint;
  `publish(replay)` ist Feuer-und-vergessen, `publish_now` synchron.
  `status` / `publish_status` sind die Texte für Menü und Death-Screen.
- Verdrahtung: `App` baut `IdentityStore(...).load_or_create()` und den
  `RunExchange`, außer `METEORITE_DASH_OFFLINE` ist gesetzt. `MainMenu.on_enter`
  → `prefetch(daily_seed(today))`. `App._create_scene`: Daily immer,
  freier Lauf nur bei erzwungenem Seed (`seed_forced()`) → `wait_for(seed,
  NOSTR_FETCH_TIMEOUT)`, danach findet `GameScene.find_ghost` den weitesten
  Lauf inklusive Community. `GameScene._store_replay` → `publish` bei jedem
  eigenen Rekord (ersetzbares Event = „mein Bestlauf zu diesem Seed“).
  `Replay.author` (Pubkey, leer bei eigenen Läufen) → `GameState.final_record_author`
  → Death-Screen „REKORD … VON <pubkey8>“ plus Zeile mit `publish_status`.
- Was das Netz sieht: Pubkey, Seed, Schiff, Zubehör, Eingaben, Endzustand —
  öffentlich und praktisch dauerhaft. Sonst nichts.
- Bestenliste: `leaderboard.build_leaderboard(store.all(), seed)` — reine
  Logik, filtert Seed + `SIM_VERSION`, bester Lauf je `author` (eigene
  Läufe `""` → ein „DU“-Eintrag), Sortierung Lichtjahre ↓, dann älteres
  Datum, dann Pubkey. `LeaderboardScene` liest nur den Store; `on_enter`/`R`
  → `exchange.prefetch(seed)`, `update` baut die Liste neu, sobald sich
  `exchange.status` ändert. Relays liefern die *neuesten* N Events
  (`NOSTR_MAX_RUNS = 100`), nicht die besten — bei sehr vielen Spielern
  fehlen alte Bestläufe, das ist die bekannte Lücke.

### Lauf per Code weitergeben (Share-Phrase)

Wie magic-wormhole, nur ohne dessen Server: die Phrase ist die Adresse, der
Relay der Briefkasten, die Simulation der Richter.

- `phrase.py`: `phrase_for_hash(state_hash)` nimmt die ersten 33 Bit des
  Hashes → drei Wörter aus `assets/words_de.txt` (2048 Wörter, ASCII,
  4–8 Buchstaben, keine Umlaut-Transliterationen, ß→ss). Deterministisch:
  gleicher Lauf = gleiche Phrase. `normalize` macht aus Nutzereingabe die
  kanonische Form (Klein, Trennzeichen egal, `ß`→`ss`), `matches(phrase, hash)`
  ist die Kollisions-/Manipulationsprüfung beim Empfang. **Wortliste ist
  eingefroren** (SHA-256 in `tests/test_phrase.py`); jede Änderung =
  `PHRASE_VERSION` erhöhen = neue Serie.
- `nostr.py`: `build_share_event` = `kind:30078`, `d = meteorite-dash:share:
  <PHRASE_VERSION>:<w1-w2-w3>`, `expiration` (NIP-40, 30 Tage). `parse_run_event`
  akzeptiert nur `d`-Tags, die zum Inhalt passen (Seed-Tag oder Phrase-Tag
  aus dem Hash) — ein Relay kann unter einer Phrase keinen anderen Lauf
  unterschieben.
- `exchange.py`: `share(replay)` (Thread) / `share_now` → `share_status`
  „CODE: … — GETEILT (n/m RELAYS)“. `start_lookup(phrase)` (Thread) /
  `lookup_now` → `Lookup(phrase, done, replay, message)`: erst lokal
  (`share-<w1-w2-w3>.json`), sonst Relays; neuester passender Lauf, der
  `headless.verify` besteht, wird gespeichert (`author` = Pubkey).
- `CodeEntryScene`: Buchstaben/Leerzeichen/Bindestrich (`event.unicode`),
  `Enter` sucht bzw. startet das Rennen, `Tab` = ansehen, `Esc` zurück; ohne
  Exchange nur schon geholte Codes aus dem Store. Ergebnis wandert über
  `GameState.pending_replay` + `Transition.START_RACE` / `SPECTATE` in
  `App._create_scene`.
- `GameScene(spectate=replay)`: Zuschauer-Modus — Eingaben aus
  `replay.inputs()`, kein Recorder, keine Münzen-Gutschrift, kein Store, kein
  Publish, Schiff des Replays; HUD „REPLAY VON <pubkey8|DIR>“; Ende (Tod oder
  Eingaben aufgebraucht) → `_end_spectate` → Death-Screen mit
  `GameState.final_spectate_author`, `last_replay = None` (nicht teilbar).
- Death-Screen: `C` = `exchange.share(last_replay)`, Zeile zeigt
  `share_status` (vor `publish_status`). Hint-Zeile wird aus den
  verfügbaren Aktionen gebaut (`_hint_line`).
- Phrase ist Adresse, kein Passwort: alles auf Nostr ist öffentlich.

### Entities & Spawner

- `Entity` (ABC): hält eine `pygame.Rect`-Hitbox im Referenzraum, bewegt sich
  pro `update(dt, player_y, speed_scale)` nach links. Subklassen überschreiben
  `_update_vertical` (Standard: keine vertikale Bewegung) und `draw(ctx)`.
  Entities halten **keine Surfaces** — `Meteorite` merkt sich nur den
  Bild-Dateinamen, `ctx.image` holt das Sprite beim Zeichnen.
- Bewegung ist **dt-basiert** (frame-rate-unabhängig) — float-Position intern,
  gerundet in `rect`. Beibehalten.
- Spawn über Fabrikfunktionen `spawn_meteorite` / `spawn_wave_enemy` /
  `spawn_hunter_enemy` mit Signatur `(rng, area)`: `area` ist die Spawn-Fläche
  im Referenzraum (immer `REFERENCE_SIZE`), keine Skalierungs-Parameter. Sie
  nehmen ein injiziertes `random.Random` → deterministisch testbar.
- Meteoriten-Größen und Bildvarianten liegen zentral in `METEORITE_VARIANTS`;
  neue Varianten dort ergänzen und weiter über `spawn_meteorite` erzeugen.
- `Spawner[T]` zieht timergesteuert aus einer **gewichteten Tabelle**
  (`SpawnEntry[T]`). Generisch über den Spawn-Typ: `Simulation` hält zwei
  Instanzen mit eigenem Timer und eigenem Seed-Stream — Gegner (`Entity`) und
  Münz-Formationen (`CoinFormation`) —, damit Münzen die Gegner-Gewichte nicht
  verwässern. Neuer Gegnertyp = neue `Entity`-Subklasse + `spawn_*`-Fabrik +
  Eintrag in `simulation.SPAWN_TABLE`. Munitions-Pickups folgen demselben
  Muster.
- `Spawner.update(dt, accept=..., interval_scale=...)` nimmt ein optionales
  Prädikat: abgelehnte Kandidaten werden bis `SPAWN_MAX_ATTEMPTS` neu
  gewürfelt, danach fällt der Spawn aus. `Simulation` nutzt das für den
  gegenseitigen Ausschluss von Gefahren und Münz-Mustern (siehe Münzen);
  `interval_scale` ist die Director-Stellgröße.

### Waffen & Munition

- `WeaponSpec` / `WeaponLoadout` in `weapons.py`: Slot 0 ist die permanente
  Standardwaffe; weitere Slots nutzen `ShipSpec.weapon_slots`. Spezialwaffen
  (später) haben feste Munition und werden bei 0 entfernt.
  `standard_ammo_bonus` vergrößert das Standard-Magazin (Zubehör
  „Extra-Munition“).
- `Projectile` in `projectiles.py` fliegt nach rechts, unabhängig von `Entity`;
  `is_off_screen` prüft gegen die Referenzbreite.
- `AmmoPickup` ist eine harmlose `Entity`-Subklasse (`damages_player = False`);
  Aufsammeln füllt die Standardwaffe über `WeaponLoadout.refill_standard()`.
- `Simulation` steuert Feuern (`InputFrame.FIRE`, Cooldown) und Waffenwechsel
  (`SWAP_WEAPON`-Flanke); `GameScene` übersetzt Tasten und zeichnet das HUD.

### Kampf

- `DamageableEntity` in `entities.py`: HP + Kollisionsschaden; Meteoriten-HP
  stehen in `MeteoriteVariant`, Gegner-HP in `config.py`.
- `combat.py`: `resolve_projectile_hits` und `apply_contact_damage` — rein
  logisch, headless testbar.
- `WeaponSpec.damage` und `WeaponSpec.fire_cooldown` pro Waffe; Standardwaffe
  verursacht 10 Schaden (großer Meteorit: 7 Treffer = volles Magazin).
- Spieler startet mit `ShipSpec.hp`; bei 0 HP → Death-Screen. Kollision
  entfernt das Hindernis und zieht `contact_damage` ab.

### Münzen (Collectibles)

- `coins.py`: `Coin(Entity)` (prozedural gezeichnete Gold-Scheibe mit
  Dreh-Animation, kein Bild-Asset), Muster-Layouts als **reine Funktionen**
  `Random -> Offsets` im Referenzraum (`LAYOUTS`), `spawn_coin_formation`
  wählt den Anker so, dass das Muster vertikal in den Referenzraum passt.
- `CoinFormation` bewegt/zeichnet seine Münzen als Einheit, zählt `collected`
  und `missed`; `collect(player_rect)` liefert ein `Pickup(coins, bonus)` — der
  Bonus fällt nur, wenn alle Münzen geholt und keine verpasst wurden.
- Münzen leben in `Simulation.formations`, **getrennt** von den tödlichen
  `entities`. Muster-Tabelle (`COIN_PATTERNS`: Name, Gewicht, Bonus) und alle
  Abstände/Farben liegen in `config.py`.
- **Spawn-Ausschluss:** Münzen und Meteoriten sind gleich schnell — eine
  Überlappung beim Spawn bliebe dauerhaft. `Simulation._accept_entity` /
  `_accept_formation` lehnen deshalb Gefahren in laufenden Mustern und Muster
  in Gefahren ab (`is_clear`, Abstand `COIN_HAZARD_CLEARANCE`). Harmlose
  Pickups sind ausgenommen. Zeichenreihenfolge: Gefahren, dann Münzen darüber.

### Shop, Zubehör & Persistenz (Issue #14)

- `progress.py`: `Progress` ist reine Logik — Guthaben (`coins`),
  `unlocked_ships`, `owned_accessories`, `owned_tints`, `equipped` (Schiffsname
  → Zubehör-IDs) und `tints` (Schiffsname → Farb-ID). Kauf-/Ausrüst-Methoden
  liefern ein `ShopResult` (`OK`, `TOO_EXPENSIVE`, `NO_FREE_SLOT`, …); die Szene
  übersetzt das in Text. Kostenlose Schiffe (`price == 0`) sind immer frei.
- `persistence.py`: `SaveStore(path)` liest/schreibt `Progress` als JSON —
  atomar (Temp-Datei + `os.replace`), defensiv geparst (`Progress.from_dict`
  verwirft falsche Typen und unbekannte IDs), kaputte/fehlende Datei → frischer
  Fortschritt, Schreibfehler → Warnung statt Crash. Pfad:
  `default_save_path()` (XDG / AppData / Application Support), überschreibbar
  per `METEORITE_DASH_SAVE_DIR`.
- Kataloge: `ShipSpec.price` in `SHIPS`, `AccessorySpec` in
  `accessories.ACCESSORIES` (Kind, Name, Beschreibung, Preis), `TintSpec` in
  `ships.TINTS`. Effektstärken (`SHIELD_CHARGES`, `MAGNET_RADIUS`,
  `AMMO_RESERVE_BONUS`, `ARMOR_HP_BONUS`) stehen in `config.py`.
- Zubehör wird **einmal gekauft** und pro Schiff ausgerüstet, begrenzt durch
  `ShipSpec.accessory_slots`. Farben ebenso: einmal kaufen, pro Schiff
  wählen; `Progress.ship_tint(spec)` liefert die effektive Färbung (gekaufte
  Farbe oder `ShipSpec.tint`).
- Effekte wendet `Simulation.__init__` aus der `RunConfig` an (Zubehör-IDs
  liefert `GameScene.run_config`): Panzerung → `Player(extra_hp=…)`,
  Extra-Munition → `WeaponLoadout(standard_ammo_bonus=…)`, Schild →
  `shield_charges` + `combat.absorb_contact` (blockt Treffer ohne Schaden,
  HUD `SCHILD xN`), Magnet → `CoinFormation.attract` zieht Münzen im Radius
  heran.
- `ShopScene` (`scenes/shop.py`): Reiter Schiffe / Zubehör / Farben, `rows()`
  baut die Zeilen aus `Progress`, `_activate` kauft/rüstet/wählt und ruft
  danach `context.save_progress()`. Wallet oben rechts über
  `scenes/widgets.draw_wallet` — auch im Hauptmenü und in der Schiffsauswahl.
- `ShipSelection` hält einen eigenen `cursor`; nur ein freigeschaltetes Schiff
  wird per Enter in `GameState.selected_ship_index` übernommen.

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
  `Viewport` und schreibt beim `DEATH`-Event `state.final_light_years`.
- `DeathScene` liest `state.final_light_years` und `state.final_coins` und zeigt
  beide auf dem Game-Over-Screen.
- Münzen: `Simulation.coins_collected` (inkl. Boni) → HUD `COINS ...` plus
  kurzer `BONUS +n`-Hinweis aus dem `COIN_BONUS`-Event; bei Tod nach
  `state.final_coins`, in `on_exit` (auch bei Escape) auf `state.progress.coins`
  addiert und gespeichert.

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
4. **Logik im Referenzraum, Rendering über `RenderContext`/`Viewport`** (siehe
   §5). Fensterpixel gehören nur in `draw`-Methoden und HUD-Code.
   Resize/Vollbild müssen weiter funktionieren.
5. **Determinismus ist Pflicht.** Zufall nur aus den Seed-Streams der
   `Simulation` (`seeded(seed, stream)`), im Sim-Pfad `mathutil.det_sin` /
   `det_hypot` statt `math`, keine Wandzeit, keine Fensterpixel. Reine
   Spiel-Logik bleibt ohne Display headless testbar (`headless.run`).
6. **dt-basierte Bewegung mit festem `SIM_DT`.** Logik bekommt `dt` nur aus
   `Simulation.step`; nichts an FPS oder Wandzeit koppeln. Render-Deko
   (Sternenfeld, HUD-Fades) darf Wandzeit nutzen.
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

- **Gegner/Hindernis:** `Entity`-Subklasse mit `draw(ctx)` und ggf.
  `state_key()` → `spawn_*`-Fabrik `(rng, area)` → Gewicht in
  `simulation.SPAWN_TABLE` → Logik-Test mit gesetztem Seed → `SIM_VERSION`
  erhöhen.
- **Waffe/Pickup:** Konstanten in `config.py`, Logik in `weapons.py` /
  `projectiles.py`, Integration in `Simulation.step` (+ passender `EventKind`),
  Sound/HUD in `GameScene._on_event`.
- **Director (#32/#33):** Klasse mit `params(sim, rng) -> DifficultyParams`
  (Protokoll in `difficulty.py`), bei internem Zustand zusätzlich
  `StatefulDirector.state_key()`, über `Simulation(director=…)` einhängen,
  Replay-/Versionsauswirkung prüfen und mit einem Headless-Test nach dem Muster
  `test_director_keeps_replays_bit_identical`.
- **Szene/Screen** (z. B. Game-Over, Issue #15): `Scene`-Subklasse +
  `Transition` + Verdrahtung in `App._create_scene`; Menüpunkte in
  `MENU_ITEMS` + `_ACTION_TRANSITIONS` (`scenes/main_menu.py`).
- **Spielzustand:** Lauf-Zustand in `Simulation` (in `state_key` und ggf.
  `Snapshot` aufnehmen), Session-Felder in `GameState`, Persistentes in
  `Progress`; HUD in `GameScene` über `Viewport`-Schrift.
- **Münz-Muster:** Layout-Funktion in `coins.py` + Eintrag in `LAYOUTS` +
  `CoinPatternSpec` in `COIN_PATTERNS` (`config.py`) → Test in
  `tests/test_coins.py` (Determinismus, passt ins Fenster).
- **Zubehör:** `AccessoryKind` + `AccessorySpec` in `accessories.py`,
  Effektstärke in `config.py`, Effekt in `Simulation.__init__` / `step` (oder
  als reine Funktion in `combat.py` / `coins.py`) → Tests in
  `tests/test_shop.py`.
  `Progress` braucht keine Änderung — IDs kommen aus dem Katalog.
- **Shop-Artikel / Farbe:** `TintSpec` in `ships.TINTS` bzw. `price` am
  `ShipSpec`; Persistenz übernimmt neue IDs automatisch, alte Speicherstände
  bleiben lesbar.
- **Neuer Transport für Läufe** (QR, Text, LAN): `sharecode.from_text` →
  dieselbe Prüfkette wie `RunExchange.import_runs` (Version, Seed, Länge,
  `headless.verify`) → `ReplayStore.save` mit `author`. Nie einen fremden
  Lauf ungeprüft ablegen. Netz nur in Threads, Spiel-Loop wartet höchstens
  `NOSTR_FETCH_TIMEOUT`.

---

## 7. Tests

- Framework: **pytest**, Tests unter `tests/`.
- **Headless:** `tests/conftest.py` setzt `SDL_VIDEODRIVER=dummy` und
  `SDL_AUDIODRIVER=dummy` (per `setdefault`, vor dem ersten `pygame`-Import), damit
  Tests ohne Display/Audio laufen. In CI sind dieselben Variablen für den
  pytest-Schritt gesetzt. Bei neuem display-/audio-berührendem Test denselben
  Weg nutzen.
- Muster: Eingaben als `InputFrame` direkt in `sim.step(...)` bzw.
  `scene.step(...)` (keine Tastatur-Monkeypatches), `GameScene(context, seed=…)`
  für reproduzierbare Szenen, `headless.run` + `scripted_inputs` für lange
  Läufe, `context`-Fixture baut einen vollständigen `GameContext` **ohne**
  `store` (kein Datei-Zugriff). Logik (`test_logic.py`), Simulation/Determinismus
  (`test_simulation.py`), Münzen (`test_coins.py`), Fortschritt/Persistenz
  (`test_progress.py`, mit `tmp_path`), Replays (`test_replay.py`, Golden in
  `tests/replays/`), Ghost (`test_ghost.py`), Daily (`test_daily.py`),
  Shop/Zubehör (`test_shop.py`), Skalierung/Resize (`test_viewport.py`),
  Share-Code (`test_sharecode.py`), Nostr (`test_nostr.py`), Bestenliste
  (`test_leaderboard.py`), Phrase (`test_phrase.py`) und Code-Weitergabe
  (`test_share.py`) sind getrennt. Der `FakeRelay` liegt in
  `tests/fake_relay.py`.
- **Kein Netz in Tests:** `conftest.py` setzt `METEORITE_DASH_OFFLINE=1`, damit
  `App()` ohne Exchange baut. Netz-Tests starten einen `FakeRelay`
  (`websockets.serve` auf 127.0.0.1, ersetzbare Events, `REQ`/`EOSE`) und
  baut `RunExchange(..., client=RelayClient([relay.url]))` explizit;
  „Relay tot“ wird mit `ws://127.0.0.1:1` geprüft.
- Neue Spiel-Logik braucht einen Test. Reine Funktionen bevorzugen, die ohne
  laufenden Loop prüfbar sind (siehe vorhandene Spawner-/Entity-/Player-Tests).

---

## 8. Security

Das Spiel ist single-player ohne Accounts oder Secrets im Spielcode; die
einzige Netzverbindung ist der freiwillige Austausch von Läufen über
öffentliche Nostr-Relays (ausgehende WebSockets, kein eigener Server). Die
realistischen Punkte:

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
- **Persistenz (`persistence.py`):** **JSON, niemals `pickle`/`eval`** auf
  nicht vertrauenswürdige Daten. `Progress.from_dict` parst defensiv (fehlende/
  falsch typisierte Felder, unbekannte IDs, `bool`-als-`int`), Datei liegt im
  nutzer-beschreibbaren Datenverzeichnis, kaputte Dateien werden toleriert.
  `Replay.from_dict` / `ReplayStore` folgen demselben Muster (Replays sind
  potenziell fremde Dateien — Ghost gegen Freunde); `path_for` bereinigt
  Dateinamen. Dieses Muster für Highscore/Settings wiederverwenden, nicht neu
  erfinden.
- **Nostr (`nostr.py`, `exchange.py`):** Relays sind fremde Server, Events
  fremde Daten. Eingehend: `parse_run_event` prüft Form, ID, Signatur und
  Größe (`NOSTR_MAX_CONTENT_CHARS`), `import_runs` deckelt Anzahl
  (`NOSTR_MAX_RUNS`) und Länge (`NOSTR_MAX_TICKS`) und spielt jeden Lauf
  nach, bevor er gespeichert wird — ein Relay kann Läufe verschweigen, aber
  keinen erfinden. Ausgehend: nur Pubkey + Replay, keine Systemdaten. Der
  private Schlüssel (`identity.json`) verlässt den Rechner nie; nicht loggen.
  Die Relay-Liste steht in `config.py` — nur `wss://`, keine Laufzeit-Konfig
  aus fremden Daten. `METEORITE_DASH_OFFLINE=1` ist der Aus-Schalter.
- **Abhängigkeiten:** über `uv` gepinnt halten; nur etablierte Pakete (pygame-ce)
  aus PyPI. Keine ungeprüften Downloads zur Laufzeit.

Es gibt hier **keine** Angriffsflächen wie Eingabe-Eval oder eingehende
Verbindungen — keine erfinden. Deserialisiert werden JSON-Speicherstand,
Replays, `identity.json` und Relay-Nachrichten (JSON, Share-Code) — alle nach
demselben defensiven Muster.

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
- **Spieler-HP aus `ShipSpec.hull`.** Kollision zieht `contact_damage` ab und
  entfernt das Hindernis; bei 0 HP → Death-Screen.
- **Kein Fenstermaß in der Logik.** `Player`, Entities und Spawner kennen nur
  `REFERENCE_SIZE`; wer `screen.get_size()` in Spiellogik zieht, bricht
  Determinismus und Replays. `GameScene` braucht deshalb kein `on_resize`.
- **Sim-Pfad ist heilig.** `math.sin`/`math.hypot`, `time`, `pygame.key`,
  ungeseedeter `random` und Set-Iteration haben in `simulation.py`,
  `entities.py`, `coins.py`, `player.py`, `spawner.py`, `combat.py` nichts
  verloren — sonst laufen Replays auseinander. Regeländerung → `SIM_VERSION`.
- **Exakte Tick-Vielfache im Test:** `scene.update(3 * SIM_DT)` liefert dank
  `_STEP_EPSILON` drei Ticks; ohne den Epsilon frisst Float-Rundung einen.
- **Threads nur im Exchange.** `RunExchange` ist der einzige Ort mit Threads;
  er fasst weder Fenster noch Simulation des laufenden Spiels an, nur Netz,
  `headless.verify` und den `ReplayStore` (atomare Dateien). Szenen lesen nur
  `status`/`publish_status`. `GameScene.__init__` setzt `publish_status`
  zurück, sonst zeigt der Death-Screen den Stand des Vorlaufs.
- **Öffentliche Relays sind flatterhaft.** Einzelne Relays antworten mit 503
  oder gar nicht — deshalb mehrere in `NOSTR_RELAYS`, Timeouts pro Verbindung
  und `relays_ok == 0` heißt „offline“, nicht „keine Läufe“.
