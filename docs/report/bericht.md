---
title: "Meteorite Dash — Projektbericht"
subtitle: "TODO: Modul/Kurs, Semester, Dozent:in"
author:
  - "TODO: Name 1 (Matrikelnummer 1)"
  - "TODO: Name 2 (Matrikelnummer 2)"
date: "2026-08-31"
lang: de
---

<!--
STATUS: Grobstruktur (Stand 2026-08-31). Kapitel 2 und Tabelle 3.6 an den
Repo-Stand angepasst (Director #32/#33, Sharing, Hitboxen, Healthbar, …).
Rest Stichpunkte. Alles mit "TODO" braucht Input der Autoren.

FORMALE KRITERIEN (Issue #27) — Checkliste vor Abgabe:
[ ] Dateiname: <Matrikel1>_<Matrikel2>_MeteoriteDash.pdf
[ ] 2–12 Seiten (ideal 6–10), Deckblatt zählt nicht, Anhang erlaubt
[ ] Zitierweise einheitlich: [n] im Text, Bibliographie nach Zitierreihenfolge
[ ] Quelltext verlinkt: https://github.com/WontExplode/meteorite-dash (public, geprüft 2026-08-31)
[ ] PDF < 20 MB (Screenshots komprimieren)
[ ] Eigenständigkeitserklärung: nur die im Bericht genannten Werkzeuge; KI-Umfang
    im Text konkret beschrieben (Kap. 2.4, 3.5–3.7)
[ ] Screenshots/Outputs als Funktionsnachweis (Kap. 4)
[ ] Keine unbegründeten Adjektive
-->

# 1 Einleitung

## 1.1 Motivation

- TODO: Warum ein Arcade-Spiel, warum Python/Pygame (persönlicher Bezug, Vorwissen,
  Wunsch nach etwas Sichtbarem statt CLI-Tool …).
- TODO: Teamkonstellation (2 Personen), Aufgabenteilung in einem Satz.

## 1.2 Zielsetzung (Variante der Projektskizze)

Ursprüngliche Skizze (aus `CLAUDE.md` §1, Stand Projektstart 2026-05-27):

- Raumschiff am linken Rand, Bewegung hoch/runter.
- Meteoriten von rechts nach links, Geschwindigkeit steigt mit der Zeit.
- Sterne einsammeln für Punkte.
- Schießen mit begrenzter Munition; Munitions-Pickups.
- Zerstörbare Meteoriten (große brauchen mehrere Treffer) und unzerstörbare.
- Kollision kostet Leben; bei null Leben Game Over.
- Erweiterungen: Highscore, Sounds, Power-ups, feindliche Schiffe, Schiffsauswahl,
  Endbosse/Level.

Umgesetzte Variante (Abweichungen kurz begründen, Details in Kap. 5.4):

- Statt „Sterne einsammeln“: Münzen in Mustern + Shop (Issue #14). Die Rolle
  „Objekt einsammeln“ ist damit belegt; `StarField` bleibt Deko.
- Statt „Leben“: HP-Modell aus Schiffsrumpf (`ShipSpec.hull`).
- Zusätzlich: deterministische Simulation, Replays, Ghost, Daily Run und
  Community-Läufe über Nostr (Issue #34).
- Steigende Schwierigkeit doch umgesetzt: Zeitrampe in beiden Modi (Issue #32)
  plus adaptiver Director im Free Mode (Issue #33).
- Unzerstörbare Meteoriten (Panzergestein, nur ausweichen).
- Dünne Lebensleiste über Gegnern/Meteoriten, sichtbar erst nach dem ersten Treffer.
- Nicht umgesetzt: Spezialwaffen-Pickups (Issue #12), Endbosse/Level (Issue #10),
  Mobile-Port (Issue #5).
- TODO: Warum die Prioritäten so gesetzt wurden.

# 2 Grundlagen & Werkzeuge

## 2.1 Technologien

| Technologie | Version | Zweck | Begründung |
|---|---|---|---|
| Python | 3.13.9 (`.python-version` → 3.13) | Sprache | TODO (Kursvorgabe? Vorwissen?) |
| pygame-ce | 2.5.7 | 2D-Rendering, Events, Audio | Community-Fork von pygame; aktiv gepflegt, Wheels für 3.13. TODO: bestätigen, dass das der Grund war |
| uv | 0.9.11 | Paket-/Umgebungsmanager, Lockfile (`uv.lock`) | reproduzierbare Umgebung lokal und in CI mit demselben Befehl (`uv sync`) |

Hinweis für den Text: Import bleibt `import pygame`, Abhängigkeit heißt `pygame-ce`.

## 2.2 Bibliotheken & Pakete

Laufzeit: Spielkern nur `pygame-ce`. Dazu zwei Netz-Abhängigkeiten für den
freiwilligen Austausch von Läufen (Issue #34, ohne eigenen Server):

| Paket | Version | Zweck |
|---|---|---|
| pygame-ce | 2.5.7 | 2D-Rendering, Events, Audio |
| coincurve | 21.0.0 | BIP-340-Schnorr für Nostr-Events (`identity.py`) |
| websockets | 17.1 | Relay-Client (`nostr.py`) |

Alles andere ist Standardbibliothek (u. a. `dataclasses`, `enum`,
`collections.abc`, `random`, `pathlib`, `math`, `json`, `hashlib`).
`METEORITE_DASH_OFFLINE=1` schaltet coincurve/websockets-Pfade ab.

Entwicklung (`[dependency-groups] dev` in `pyproject.toml`):

| Werkzeug | Version | Rolle |
|---|---|---|
| ruff | 0.15.15 | Formatierung + Linting (Regelgruppen F, E, W, I, N, UP, B, SIM, RUF; `line-length = 100`) |
| mypy | 2.1.0 | Typprüfung `--strict` über `src` und `tests` |
| pytest | 9.0.3 | Tests, headless über `SDL_VIDEODRIVER=dummy` / `SDL_AUDIODRIVER=dummy`; Doctests via `--doctest-modules` |
| interrogate | 1.7.0 | Docstring-Abdeckung (`fail-under = 80`) |

- TODO: Warum strict-Typisierung und Linter in einem Spielprojekt (Begründung:
  KI-generierter Code braucht mechanische Leitplanken? Teamgröße 2?).

## 2.3 Entwicklungsworkflow & Infrastruktur

Kennzahlen (Stand 2026-08-31, aus `git`/`gh`):

- Repository: GitHub-Organisation `WontExplode`, Repo `meteorite-dash`
  (öffentlich: https://github.com/WontExplode/meteorite-dash).
- 146 Commits, 2026-05-27 bis 2026-08-31, 28 gemergte Pull Requests.
- Issues als Feature-Backlog (`gh issue list`): TODO aktuelle Zahl nachziehen
  (Stand 2026-08-30: 24 Issues, davon 12 geschlossen).
- Umfang: ca. 7 800 Zeilen in `src/`, ca. 4 500 Zeilen in `tests/`, 442 Tests
  inkl. Doctests (`uv run pytest --collect-only`: `442 tests collected`).
- Git-Identitäten: `Julian Schiebener` (60 Commits), `Marco`/`MPReimann`/`cakebomb999`
  (83 Commits — TODO: bestätigen, dass das eine Person ist), `claude[bot]` (3 Commits).

Prozess:

- Feature-Branches + PR auf `main`; Merge nach Review.
- CI (`.github/workflows/ci.yml`, GitHub Actions): `ruff format --check`,
  `ruff check`, `mypy`, `pytest`, `interrogate` — bei Push auf `main` und jedem PR.
- Pre-commit-Hook (`.githooks/pre-commit`) führt dieselben fünf Checks lokal aus.
- `CLAUDE.md` im Repo: Architektur-Leitfaden für Menschen und KI (Konventionen,
  Referenzraum-Regel, Testpflicht).
- Design-Spezifikationen vor der Implementierung in `docs/superpowers/specs/`
  (3 Specs: OO-Umbau, Meteoriten/Gegner, Schiffssystem) + 1 Implementierungsplan.

## 2.4 Mensch vs. KI: Die Rolle von AI Assistance

Eingesetzte KI-Werkzeuge (nur diese dürfen laut Eigenständigkeitserklärung genutzt
worden sein — TODO: Liste vollständig machen, ggf. ChatGPT/Copilot/andere ergänzen
oder explizit ausschließen):

1. **Claude Code** (Anthropic, CLI) als Pair-Programming-Assistent im Terminal.
   TODO: Modelle (Opus/Sonnet/…), Zeitraum, wer im Team hat es wie intensiv genutzt.
2. **Superpowers-Workflow** (Claude-Code-Plugin): Brainstorm → Design-Spec →
   Implementierungsplan → Umsetzung Task für Task. Belege: `docs/superpowers/`.
3. **Claude Code GitHub Action** (`anthropics/claude-code-action@v1`):
   - `claude-code-review.yml`: automatisches PR-Review bei Änderungen in `src/**`,
     Modell `sonnet`, max. 10 Turns, Prompt beschränkt auf neue Bugs und
     `CLAUDE.md`-Verstöße („Keine Stilfragen, nichts, was Linter oder Typechecker
     ohnehin finden“).
   - `claude.yml`: reagiert auf `@claude`-Mentions in Issues/PRs; hat 3 Commits
     erzeugt (u. a. Test für `set_vertical_position`, Konstanten nach `config.py`,
     Share-Thread-Fix).
4. **GitHub Code Scanning / Copilot Autofix**: Commits „Potential fix for pull
   request finding 'Statement has no effect'“ (3×) — TODO: bestätigen, welches
   Werkzeug das war.
5. TODO: Assets — wurden Bilder/Sounds KI-generiert? Wenn ja, Werkzeug nennen.

Abgrenzung in einem Absatz: KI schreibt Code-Vorschläge, Mensch entscheidet
Architektur, prüft Diffs, mergt. Details zu Umfang je Modul in Kap. 3.6.

# 3 Konzept & Implementierung

## 3.1 Programmstruktur

- Datenfluss: `main.py` → `App` → aktive `Scene` → `Transition` → nächste Szene.
- Szenen: `MainMenu`, `ShipSelection`, `ShopScene`, `LoadoutScene`,
  `LeaderboardScene`, `CodeEntryScene`, `GameScene`, `DeathScene`;
  gemeinsame Basis `Scene` (Template-Method-Loop, 60 FPS, globale Events).
- `GameContext` als geteilter Zustands-/Ressourcen-Container (Screen, Fonts,
  Musik, Assets, `GameState`, `Progress`, `Viewport`, `ReplayStore`, `RunExchange`).
- Modulschnitt: eine Verantwortung pro Datei (Liste aus `README.md`).
- Abbildung: Modul-/Szenen-Diagramm (TODO: zeichnen).

## 3.2 Kernlogik

- `Simulation` (`simulation.py`): fester Zeitschritt `SIM_DT`, Seed-Streams,
  Eingaben als `InputFrame` (Bitmaske), `SimEvent` mit Snapshot.
- Entities (`entities.py`): `Entity` → `DamageableEntity` → `Meteorite`,
  `IndestructibleMeteorite`, `WaveEnemy`, `HunterEnemy`; `AmmoPickup`;
  dt-basierte Bewegung.
- `Spawner`: gewichtete Tabelle `SpawnEntry`, timergesteuert, injiziertes
  `random.Random`.
- Kampf: `combat.py` (`resolve_projectile_hits`, `apply_contact_damage`),
  `weapons.py` (`WeaponSpec`, `WeaponLoadout`), `projectiles.py`.
- Hitboxen: `hitbox.py` — Maske neben `rect`, pixelgenau über `overlaps`.
- Schiffe: `ShipSpec` mit physikalischen Grundwerten (mass/thrust/hull), abgeleitete
  Werte (`acceleration = thrust/mass`, `max_speed = thrust/DRAG`, …).
- Münzen/Shop/Ausrüstung: `CoinFormation`-Muster, `Progress` + `persistence.py`,
  Zubehör als Verbrauchsware (`LoadoutScene`).
- Schwierigkeit: `Director`-Vertrag (`difficulty.py`); `RampDirector` (Issue #32)
  in jedem Modus; `AdaptiveDirector` (Issue #33) nur im Free Mode, multipliziert
  über `CompositeDirector`; Modusgrenze in `mode_directors.py`.
- Replay/Ghost/Daily: `Recorder` → `Replay` (RLE), `headless.verify`, `ghost.py`
  als zweite `Simulation` im Gleichschritt, `daily.py` (SHA-256 aus Salt + UTC-Datum).
- Community: `nostr.py`/`exchange.py` (Relays), `sharecode.py`, `phrase.py`
  (Drei-Wort-Code), `leaderboard.py` (Top 5 zum Tages-Seed).
- Feedback (reines Rendering): `effects.py` (Funken, Blitz, Erschütterung,
  Lebensleisten), `sfx.py` (prozedurale Sounds), `menu_fx.py` (Hauptmenü-Deko).

## 3.3 Datenverarbeitung

- Referenzraum 800×600: Simulation rechnet nur dort; `Viewport`/`RenderContext`
  skalieren beim Zeichnen (`px`/`py` pro Achse, `s()` höhen-gebunden).
- Persistenz: `progress.json` im Nutzer-Datenverzeichnis, defensives Parsen,
  kein `pickle`.
- Replay-Format: `RunConfig` + Eingaben (RLE) als JSON; `state_hash()` als
  Gleichheitsbeweis; Golden-Dateien `tests/replays/golden-*.json`.
- TODO: ein Beispiel-JSON (gekürzt) in den Anhang.

## 3.4 Warum so? Verworfene Alternativen

Aus den Specs belegbar:

- Schlichte Klassen + Listen statt `pygame.sprite`-Groups (Spec 2026-05-29):
  Testbarkeit ohne Display, Konsistenz mit `Player`.
- Szenenwechsel per Rückgabewert (`Transition`) statt Stack-basiertem
  `SceneManager` (Spec OO-Umbau): „pragmatisch-schlank“.
- Randloses Strecken pro Achse statt Letterbox (Issue #6): TODO Begründung.
- Trennung Simulation/Rendering (PR #38/#41): Resize darf Spielzustand nicht
  ändern; Determinismus als Voraussetzung für Replay/Ghost.
- Öffentliche Nostr-Relays statt eigenem Server (Issue #34): Replay-Datei ist
  die Upload-Einheit, `headless.verify` der Richter.
- TODO: Wo war die Wahl willkürlich? (z. B. Zahlenwerte in `config.py`,
  Münz-Muster, 7 Schuss Munition).

## 3.5 KI-Konsultation bei Design-Entscheidungen

- Belege: die drei Design-Specs entstanden im Brainstorm-Dialog mit Claude Code
  („Gewählter Ansatz“ jeweils aus mehreren Optionen).
- TODO: Welche KI-Vorschläge wurden übernommen (z. B. `Entity`-ABC, Spawner-Tabelle)?
- TODO: Wo bewusst abgewichen (z. B. kein AssetManager-Caching „über das Nötige
  hinaus“, keine `pygame.sprite`)? Warum?

## 3.6 Code-Generierung: KI-generiert vs. selbst programmiert

Tabelle je Modul/Feature (TODO ausfüllen — Git-Historie als Ausgangspunkt):

| Feature / Modul | PR | Autor:in | Anteil KI | Anmerkung |
|---|---|---|---|---|
| OO-Umbau (`app.py`, `scenes/base.py`, `context.py`) | #17 | Marco | TODO | Spec + Plan via Superpowers |
| Meteoriten/Gegner/Spawner | #19 | Marco | TODO | |
| Sternenfeld (`starfield.py`) | #18 | Julian | TODO | |
| Dynamische Fenstergröße / `Viewport` | #20 | Marco | TODO | |
| Death-Screen | #22, #24 | Julian | TODO | |
| Meteoriten-Varianten, Assets, Schiffsauswahl | #30 | Julian | TODO | |
| Schiffssystem (`ships.py`) | #29 | Marco | TODO | |
| Waffen, Munition, Schaden (`weapons.py`, `combat.py`) | #31 | Julian | TODO | |
| Münzen + Shop + Persistenz | #40 | Marco | TODO | |
| Simulation / Replay / Ghost / Daily | #41–#44 | Marco | TODO | |
| Adaptiver Schwierigkeits-Director (`adaptive_difficulty.py`, `mode_directors.py`) | #48, #49, #52, #54 | Julian | TODO | Free = Rampe × adaptiv; Daily = pure Rampe; Zustand im Hash; F3-Diagnose-HUD |
| Zeitrampe (`ramp_difficulty.py`) | #59 | Marco | TODO | Issue #32; beide Modi, Spawn-Intervalle schrumpfen mit |
| Community / Nostr / Share-Code / Bestenliste | #53 | Marco | TODO | Relays statt eigenem Server; Phrase + Zuschauen/Rennen |
| Pixelgenaue Hitboxen (`hitbox.py`) + Treffer-Feedback (`effects.py`, `sfx.py`) | #59 | Marco | TODO | Masken in Referenzgröße; prozedurale Sounds |
| Hauptmenü-Deko (`menu_fx.py`) | #59 | Marco | TODO | Sternenfeld, Scanlines, prallende Deko-Meteoriten |
| Zubehör als Verbrauchsware (`LoadoutScene`) | #59 | Marco | TODO | Vorrat kaufen, vor dem Lauf auf Plätze legen |
| Unzerstörbare Meteoriten | #60 | Marco | TODO | Panzergestein, wandernde Lichtstreifen |
| Lebensleisten über getroffenen Zielen | — | Julian | TODO | Sichtbar erst nach dem ersten Treffer; Aufleuchten + Wackeln. Branch `minimal-healthbar` |
| Tests (`tests/`) | alle | beide | TODO | |
| CI, Hooks, `CLAUDE.md` | #2–#4, #21 | Marco | TODO | später + `interrogate` (#47) |

- Warum KI hier sinnvoll (Boilerplate, Tests, Typ-Annotationen …) — TODO.
- Wo eigene Programmierung nötig (KI verstand Kontext nicht, fehlerhafter Code) — TODO
  mit konkreten Beispielen.

## 3.7 Prompt-Engineering & Iteration

- Arbeitsweise: Spec freigeben → Plan → Umsetzung → Diff lesen → Checks → PR →
  Review-Bot → Merge. TODO: stimmt das so für beide?
- Leitplanken: `CLAUDE.md` (Regeln, Gotchas), strict mypy/ruff als Filter für
  KI-Fehler.
- TODO: 2–3 konkrete Iterationsschleifen (Halluzination, veraltete API,
  falscher Ansatz) mit Ausgang.
- TODO: Beispiel-Prompt (gekürzt) in den Anhang.

# 4 Ergebnisse

## 4.1 Funktionsnachweis

- Screenshots (TODO anfertigen, PNG komprimiert): Hauptmenü (Endgame-Look),
  Schiffsauswahl, Ausrüstung, Spiel mit HUD (Lightyears, Münzen, Waffe,
  Ghost-Δ, Lebensleiste nach Treffer), Shop, Daily-Bestenliste, Code-Eingabe,
  Death-Screen, optional F3-Diagnose-HUD.
- Test-Output: `442 tests collected` (Stand 2026-08-31, inkl. Doctests);
  CI-Lauf grün (Screenshot oder Link).
- Replay-Prüfung: Ausgabe von `uv run meteorite-dash --verify datei.json`
  (Trace + `PASS`).

## 4.2 Beispiel-Durchlauf

- Daily Run mit festem Seed (`METEORITE_DASH_SEED`), Replay als `best.json`,
  zweiter Lauf mit Ghost, Vergleich auf dem Death-Screen.
- Free Mode: Zeitrampe plus adaptiver Director (F3 zeigt Intensität).
- Determinismus-Beleg: gleicher `state_hash()` bei zweifacher headless-Ausführung.

# 5 Diskussion & Fazit

## 5.1 Zielerreichung

- Kern-Loop der Skizze vollständig; Erweiterungen teils über die Skizze hinaus
  (Replay/Ghost/Daily/Nostr, Director #32/#33), teils bewusst anders (Münzen
  statt Sterne). Offen bleiben Spezialwaffen, Bosse, Mobile (siehe 1.2 / 5.5).

## 5.2 Herausforderungen

- TODO technisch: Resize/Vollbild-Bug (Issue #28), Determinismus
  (plattformstabiler Sinus in `mathutil.py`), Merge-Konflikte bei parallelen
  Feature-Branches (PR #37 geschlossen, #40 neu; später Adaptive vs. Sharing
  #52/#53/#54).
- TODO Zusammenarbeit mit KI: konkrete Fälle.

## 5.3 Kritische Reflexion

- TODO: Was lief gut, was nicht; Qualität des KI-Codes; Aufwand fürs Review.

## 5.4 Abweichung vom ursprünglichen Plan

- Sterne → Münzen/Shop (dieselbe Sammel-Aktion, zusätzlich persistentes Guthaben).
- Leben → HP aus `ShipSpec.hull`.
- Unzerstörbare Meteoriten nachgezogen (Skizze, #60).
- Schwierigkeitskurve nicht statt Replay, sondern darauf: Director-Vertrag in
  der Simulation (#34), Zeitrampe (#32) und adaptiver Free-Mode (#33) danach.
- TODO: Gründe.

## 5.5 Ausblick

- Offene Issues bzw. Lücken: #12 Waffen-Upgrades/Spezialwaffen, #10 Bosse/Level,
  #13 Spieler-Stats, #5 Mobile-Port, #35 2D-Bewegung, #36 Boost.
- Director: Speed, Gefahrenintervall und Score-Faktor stehen; Gegnermix,
  Größenbias und Schwarm-Events fehlen noch.
- Sharing: QR-Anzeige des Share-Codes, Freunde-Filter nach Pubkey in der
  Bestenliste. Eigener Server unnötig — Relays + `headless.verify` prüfen Läufe.

# Literatur- & Quellenverzeichnis

Nummeriert nach Zitierreihenfolge `[n]`. Nur eintragen, was im Text zitiert wird.

- [1] pygame-ce Dokumentation — https://pyga.me/docs/  (TODO: Zugriffsdatum)
- [2] uv Dokumentation — https://docs.astral.sh/uv/
- [3] ruff — https://docs.astral.sh/ruff/
- [4] mypy — https://mypy.readthedocs.io/
- [5] pytest — https://docs.pytest.org/
- [6] Claude Code Dokumentation — https://docs.claude.com/en/docs/claude-code/
- [7] claude-code-action — https://github.com/anthropics/claude-code-action
- [8] TODO: Quellen der Grafik-Assets (`AsteroidTiny…Large`, `CopperShip…GoldShip`)
  und Musik/Sounds (`gamemusic1-3.mp3`, `menumusic.mp3`, `gameovermusic.mp3`,
  `standard-gun.mp3`) — im Repo liegt keine Lizenz-/Attributionsdatei.

# Anhang

## A Bedienungsanleitung

- Installation: `uv sync`, Start: `uv run meteorite-dash`.
- Steuerung (aus `README.md`): Pfeiltasten, `Space` schießen, `R` Waffe,
  `Enter` bestätigen, `Escape` zurück, `F`/`F11` Vollbild, `F3` Difficulty-HUD,
  `C` Code teilen, `Tab` Bestenliste (nach Daily).
- Ausrüstung vor dem Lauf: `Space` setzt Zubehör ein/ab, `Enter` startet.
- Umgebungsvariablen: `METEORITE_DASH_SEED`, `METEORITE_DASH_SAVE_DIR`,
  `METEORITE_DASH_OFFLINE=1`.
- Replay prüfen: `uv run meteorite-dash --verify datei.json`.
- Community: `uv run meteorite-dash --publish datei.json`,
  `uv run meteorite-dash --fetch <seed>`.

## B Ausgewählte Code-Snippets (max. 1 Seite je Snippet)

- TODO: `Simulation.step` (fester Zeitschritt), `Viewport.px/py/s`,
  `ShipSpec`-Properties, `Spawner`-Tabelle, `AdaptiveDirector.params`.

## C Beispiel-Prompt und KI-Antwort (gekürzt)

- TODO.

# Eigenständigkeitserklärung

TODO: Text der Hochschule/des Kurses übernehmen. Muss enthalten: Es wurden
ausschließlich die in Kap. 2.4 genannten Werkzeuge genutzt; der Umfang der
KI-Nutzung ist in Kap. 2.4 und 3.5–3.7 beschrieben.

Ort, Datum, Unterschriften beider Autor:innen.
