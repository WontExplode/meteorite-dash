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
- Strikte Typprüfung, Linting, Tests, CI.

**Noch NICHT vorhanden** (aus dem Spec — meist als GitHub-Issue getrackt):

- **Sammelbare Sterne** für Punkte (`StarField` ist nur Deko, nicht einsammelbar).
- **Spezialwaffen-Pickups** (Loadout und Slot-Limit sind vorbereitet).
- **Unzerstörbare Meteoriten** (zerstörbare Varianten mit HP sind implementiert).
- **Steigende Schwierigkeit** über die Zeit (Speed ist momentan konstant).
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
      ├─ ShopScene          Münzen gegen Schiffe, Zubehör, Farben
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
`selected_ship_index`, `final_light_years`, `final_coins` und den persistenten
`progress`); neue Session-Felder (Leben, Munition …) kommen hierher, alles, was
über den Neustart hinaus gelten soll, in `Progress`. `GameContext.store`
(`SaveStore | None`) schreibt den Fortschritt; `save_progress()` ist ohne Store
(Tests) ein No-op.

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
- `Spawner[T]` zieht timergesteuert aus einer **gewichteten Tabelle**
  (`SpawnEntry[T]`). Generisch über den Spawn-Typ: `GameScene` hält zwei
  Instanzen mit eigenem Timer — Gegner (`Entity`) und Münz-Formationen
  (`CoinFormation`) —, damit Münzen die Gegner-Gewichte nicht verwässern.
  Neuer Gegnertyp = neue `Entity`-Subklasse + `spawn_*`-Fabrik + Eintrag in
  `GameScene._spawn_table`. Munitions-Pickups folgen demselben Muster.
- `Spawner.update(dt, accept=...)` nimmt ein optionales Prädikat: abgelehnte
  Kandidaten werden bis `SPAWN_MAX_ATTEMPTS` neu gewürfelt, danach fällt der
  Spawn aus. `GameScene` nutzt das für den gegenseitigen Ausschluss von
  Gefahren und Münz-Mustern (siehe Münzen).

### Waffen & Munition

- `WeaponSpec` / `WeaponLoadout` in `weapons.py`: Slot 0 ist die permanente
  Standardwaffe; weitere Slots nutzen `ShipSpec.weapon_slots`. Spezialwaffen
  (später) haben feste Munition und werden bei 0 entfernt.
  `standard_ammo_bonus` vergrößert das Standard-Magazin (Zubehör
  „Extra-Munition“).
- `Projectile` in `projectiles.py` fliegt nach rechts, unabhängig von `Entity`.
- `AmmoPickup` ist eine harmlose `Entity`-Subklasse (`damages_player = False`);
  Aufsammeln füllt die Standardwaffe über `WeaponLoadout.refill_standard()`.
- `GameScene` steuert Feuern (`Space`, Cooldown), Waffenwechsel (`R`) und HUD.

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
  skaliert Offsets (`sx`/`sy`) und Größe (`su`) und wählt den Anker so, dass
  das Muster vertikal ins Fenster passt.
- `CoinFormation` bewegt/zeichnet seine Münzen als Einheit, zählt `collected`
  und `missed`; `collect(player_rect)` liefert ein `Pickup(coins, bonus)` — der
  Bonus fällt nur, wenn alle Münzen geholt und keine verpasst wurden.
- Münzen leben in `GameScene.formations`, **getrennt** von den tödlichen
  `entities`. Muster-Tabelle (`COIN_PATTERNS`: Name, Gewicht, Bonus) und alle
  Abstände/Farben liegen in `config.py`.
- **Spawn-Ausschluss:** Münzen und Meteoriten sind gleich schnell — eine
  Überlappung beim Spawn bliebe dauerhaft. `GameScene._accept_entity` /
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
- Effekte wendet `GameScene._build` an: Panzerung → `Player(extra_hp=…)`,
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
  `Viewport` und schreibt bei Kollision `state.final_light_years`.
- `DeathScene` liest `state.final_light_years` und `state.final_coins` und zeigt
  beide auf dem Game-Over-Screen.
- Münzen: `GameScene.coins_collected` (inkl. Boni) → HUD `COINS ...` plus
  kurzer `BONUS +n`-Hinweis; bei Tod nach `state.final_coins`, in `on_exit`
  (auch bei Escape) auf `state.progress.coins` addiert und gespeichert.

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
- **Waffe/Pickup:** Konstanten in `config.py`, Logik in `weapons.py` /
  `projectiles.py`, Integration in `GameScene`.
- **Szene/Screen** (z. B. Game-Over, Issue #15): `Scene`-Subklasse +
  `Transition` + Verdrahtung in `App._create_scene`.
- **Spielzustand** (Leben/Munition/Highscore): Felder in `GameState`, in
  `GameScene` fortschreiben, über `Viewport`-Schrift im HUD rendern.
- **Münz-Muster:** Layout-Funktion in `coins.py` + Eintrag in `LAYOUTS` +
  `CoinPatternSpec` in `COIN_PATTERNS` (`config.py`) → Test in
  `tests/test_coins.py` (Determinismus, passt ins Fenster).
- **Zubehör:** `AccessoryKind` + `AccessorySpec` in `accessories.py`,
  Effektstärke in `config.py`, Effekt in `GameScene._build` (oder als reine
  Funktion in `combat.py` / `coins.py`) → Tests in `tests/test_shop.py`.
  `Progress` braucht keine Änderung — IDs kommen aus dem Katalog.
- **Shop-Artikel / Farbe:** `TintSpec` in `ships.TINTS` bzw. `price` am
  `ShipSpec`; Persistenz übernimmt neue IDs automatisch, alte Speicherstände
  bleiben lesbar.

---

## 7. Tests

- Framework: **pytest**, Tests unter `tests/`.
- **Headless:** `tests/conftest.py` setzt `SDL_VIDEODRIVER=dummy` und
  `SDL_AUDIODRIVER=dummy` (per `setdefault`, vor dem ersten `pygame`-Import), damit
  Tests ohne Display/Audio laufen. In CI sind dieselben Variablen für den
  pytest-Schritt gesetzt. Bei neuem display-/audio-berührendem Test denselben
  Weg nutzen.
- Muster: `FakeKeys` für Tastatur, gesetzter RNG-Seed, `context`-Fixture baut
  einen vollständigen `GameContext` **ohne** `store` (kein Datei-Zugriff).
  Logik (`test_logic.py`), Münzen (`test_coins.py`), Fortschritt/Persistenz
  (`test_progress.py`, mit `tmp_path`), Shop/Zubehör (`test_shop.py`) und
  Skalierung/Resize (`test_viewport.py`) sind getrennt.
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
- **Persistenz (`persistence.py`):** **JSON, niemals `pickle`/`eval`** auf
  nicht vertrauenswürdige Daten. `Progress.from_dict` parst defensiv (fehlende/
  falsch typisierte Felder, unbekannte IDs, `bool`-als-`int`), Datei liegt im
  nutzer-beschreibbaren Datenverzeichnis, kaputte Dateien werden toleriert.
  Dieses Muster für Highscore/Settings wiederverwenden, nicht neu erfinden.
- **Abhängigkeiten:** über `uv` gepinnt halten; nur etablierte Pakete (pygame-ce)
  aus PyPI. Keine ungeprüften Downloads zur Laufzeit.

Es gibt hier **keine** echten Angriffsflächen wie Eingabe-Eval oder Netzwerk —
keine erfinden. Die einzige Deserialisierung ist der JSON-Speicherstand (siehe
oben); defensiv bleiben, sobald nutzergelieferte Inhalte dazukommen.

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
- **`Player.update` clampt nur Bewegung**, holt das Schiff aber nicht aus dem Bild
  zurück — `GameScene.on_resize` re-klemmt es nach einem Resize aktiv.
