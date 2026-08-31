"""Deterministischer Spielkern (Issue #34).

`Simulation` hält den kompletten Zustand eines Laufs und kennt weder Fenster,
Wandzeit noch Tastatur: `step(inputs)` rückt genau einen festen Zeitschritt
(`SIM_DT`) vor. Jeder Zufall stammt aus Streams, die vom Seed abgeleitet sind
(`seeded(seed, "spawn")`, …) — gleicher Seed + gleiche Eingabefolge ergibt
bit-gleich denselben Zustand, egal ob live gespielt, als Ghost wiedergegeben
oder headless im Test geprüft. Jede Interaktion (Schuss, Treffer, Pickup, Münze,
Kollision, Tod) liefert ein `SimEvent` mit dem Zustand unmittelbar danach.
"""

import functools
import hashlib
import os
import random
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple

from meteorite_dash.accessories import ACCESSORIES_BY_ID, AccessoryKind
from meteorite_dash.coins import CoinFormation, coin_rects, is_clear, spawn_coin_formation
from meteorite_dash.combat import absorb_contact, apply_contact_damage, resolve_projectile_hits
from meteorite_dash.config import (
    AMMO_PICKUP_WEIGHT,
    AMMO_RESERVE_BONUS,
    ARMOR_HP_BONUS,
    COIN_HAZARD_CLEARANCE,
    COIN_PATTERNS,
    COIN_SPAWN_INTERVAL_RANGE,
    HUNTER_ENEMY_WEIGHT,
    MAGNET_PULL_SPEED,
    MAGNET_RADIUS,
    METEORITE_WEIGHT,
    PLAYER_START_POSITION,
    REFERENCE_SIZE,
    SCORE_LIGHT_YEARS_PER_SECOND,
    SEED_BITS,
    SEED_ENV,
    SHIELD_CHARGES,
    SIM_DT,
    SPAWN_INTERVAL_RANGE,
    WAVE_ENEMY_WEIGHT,
)
from meteorite_dash.difficulty import (
    ConstantDirector,
    DifficultyParams,
    Director,
    StatefulDirector,
)
from meteorite_dash.entities import (
    Entity,
    collect_pickups,
    spawn_ammo_pickup,
    spawn_hunter_enemy,
    spawn_meteorite,
    spawn_wave_enemy,
)
from meteorite_dash.inputs import InputFrame
from meteorite_dash.player import Player
from meteorite_dash.projectiles import Projectile, spawn_projectile
from meteorite_dash.score import DistanceScore
from meteorite_dash.ships import SHIPS_BY_NAME, ShipSpec
from meteorite_dash.spawner import SpawnEntry, Spawner
from meteorite_dash.weapons import WeaponLoadout

# Spawn-Tabellen sind fensterunabhängig: alle Fabriken arbeiten im Referenzraum.
SPAWN_TABLE: tuple[SpawnEntry[Entity], ...] = (
    SpawnEntry(METEORITE_WEIGHT, spawn_meteorite),
    SpawnEntry(WAVE_ENEMY_WEIGHT, spawn_wave_enemy),
    SpawnEntry(HUNTER_ENEMY_WEIGHT, spawn_hunter_enemy),
    SpawnEntry(AMMO_PICKUP_WEIGHT, spawn_ammo_pickup),
)
COIN_TABLE: tuple[SpawnEntry[CoinFormation], ...] = tuple(
    SpawnEntry(pattern.weight, functools.partial(spawn_coin_formation, pattern=pattern))
    for pattern in COIN_PATTERNS
)


def seeded(seed: int, stream: str) -> random.Random:
    """Eigener RNG-Stream pro Konsument: zusätzliche Würfe an einer Stelle
    (z. B. ein neuer Director) verschieben die Würfe der anderen nicht."""
    return random.Random(f"{seed}:{stream}")


def seed_forced() -> bool:
    """True, wenn `METEORITE_DASH_SEED` gesetzt ist — jemand will genau diesen Lauf."""
    return bool(os.environ.get(SEED_ENV))


def pick_seed() -> int:
    """Zufälliger Seed für einen freien Lauf; `METEORITE_DASH_SEED` erzwingt einen."""
    override = os.environ.get(SEED_ENV)
    if override:
        try:
            return int(override) % (1 << SEED_BITS)
        except ValueError:
            pass
    return random.SystemRandom().getrandbits(SEED_BITS)


@dataclass(frozen=True)
class RunConfig:
    """Alles, was außer den Eingaben einen Lauf bestimmt."""

    seed: int
    ship: str  # `ShipSpec.name`
    accessories: tuple[str, ...] = ()  # ausgerüstete Zubehör-IDs (Slot-Reihenfolge)

    def __post_init__(self) -> None:
        if self.ship not in SHIPS_BY_NAME:
            raise ValueError(f"Unbekanntes Schiff: {self.ship!r}")
        for acc_id in self.accessories:
            if acc_id not in ACCESSORIES_BY_ID:
                raise ValueError(f"Unbekanntes Zubehör: {acc_id!r}")

    @property
    def spec(self) -> ShipSpec:
        """Datenblatt des gewählten Schiffs."""
        return SHIPS_BY_NAME[self.ship]

    @property
    def accessory_kinds(self) -> set[AccessoryKind]:
        """Arten des ausgerüsteten Zubehörs; Effekte werden pro Art angewendet."""
        return {ACCESSORIES_BY_ID[acc_id].kind for acc_id in self.accessories}


class EventKind(Enum):
    """Art einer Interaktion; jede erzeugt in `Simulation.step` ein `SimEvent`."""

    FIRED = "fired"
    HIT = "hit"  # Projektil trifft
    DESTROYED = "destroyed"  # Ziel zerstört
    AMMO_PICKUP = "ammo_pickup"
    COIN = "coin"
    COIN_BONUS = "coin_bonus"
    SHIELD = "shield"  # Schild blockt Kollision
    CONTACT = "contact"  # Kollisionsschaden
    DEATH = "death"


class Snapshot(NamedTuple):
    """Die Werte, die nach jeder Interaktion stimmen müssen."""

    tick: int
    hp: int
    ammo: int
    light_years: float
    coins: int
    shield: int


class SimEvent(NamedTuple):
    """Eine Interaktion mit dem Zustand unmittelbar danach.

    `GameScene` reagiert nur hierauf (Sound, Funken, Hinweise, Death-Screen);
    der `headless.Trace` besteht aus diesen Events. `sound` und `position` sind
    reine Render-Hinweise und gehören nicht zum Zustand.
    """

    kind: EventKind
    snapshot: Snapshot  # Zustand unmittelbar nach der Interaktion
    value: int = 0  # Schaden, Münzwert, Bonus — je nach Art
    sound: str | None = None  # nur für die Szene; nicht Teil des Zustands
    # Wo es passiert ist (Referenzraum) — Ankerpunkt für Funken und Explosionen.
    position: tuple[int, int] = (0, 0)


class Simulation:
    """Kompletter Zustand eines Laufs, angetrieben durch `step(inputs)`.

    Wendet beim Aufbau die Zubehör-Effekte aus der `RunConfig` an (Panzerung,
    Extra-Munition, Schild, Magnet) und hält zwei Spawner mit eigenen
    Seed-Streams: Gefahren und Münz-Formationen. Der Director bekommt pro
    Tick den Stream `<seed>:director`.
    """

    def __init__(self, config: RunConfig, *, director: Director | None = None) -> None:
        self.config = config
        spec = config.spec
        kinds = config.accessory_kinds
        extra_hp = ARMOR_HP_BONUS if AccessoryKind.ARMOR in kinds else 0
        self.player = Player(PLAYER_START_POSITION, spec, extra_hp=extra_hp)
        ammo_bonus = AMMO_RESERVE_BONUS if AccessoryKind.AMMO_RESERVE in kinds else 0
        self.loadout = WeaponLoadout(spec.weapon_slots, standard_ammo_bonus=ammo_bonus)
        self.shield_charges = SHIELD_CHARGES if AccessoryKind.SHIELD in kinds else 0
        self.magnet_enabled = AccessoryKind.MAGNET in kinds
        self.entities: list[Entity] = []
        self.projectiles: list[Projectile] = []
        # Münzen leben getrennt von `entities`: Berührung sammelt ein, schadet nicht.
        self.formations: list[CoinFormation] = []
        self.coins_collected = 0
        self.score = DistanceScore(SCORE_LIGHT_YEARS_PER_SECOND)
        self.tick = 0
        self.is_over = False
        self._shoot_cooldown = 0.0
        self.spawner = Spawner(
            SPAWN_TABLE, REFERENCE_SIZE, seeded(config.seed, "spawn"), SPAWN_INTERVAL_RANGE
        )
        self.coin_spawner = Spawner(
            COIN_TABLE, REFERENCE_SIZE, seeded(config.seed, "coins"), COIN_SPAWN_INTERVAL_RANGE
        )
        self.director: Director = director if director is not None else ConstantDirector()
        self._director_rng = seeded(config.seed, "director")
        self.difficulty = DifficultyParams()

    # --- Abfragen -------------------------------------------------------------

    @property
    def light_years(self) -> float:
        """Bisher zurückgelegte Strecke."""
        return self.score.light_years

    def snapshot(self) -> Snapshot:
        """Die prüfbaren Werte des aktuellen Ticks (für Events und Replays)."""
        return Snapshot(
            tick=self.tick,
            hp=self.player.hp,
            ammo=self.loadout.active.ammo,
            light_years=self.score.light_years,
            coins=self.coins_collected,
            shield=self.shield_charges,
        )

    def state_key(self) -> tuple[object, ...]:
        """Kompletter Zustand inklusive RNG-Streams, kanonisch und verlustfrei."""
        state = (
            self.tick,
            self.is_over,
            self.player.state_key(),
            self.loadout.state_key(),
            self.shield_charges,
            self.magnet_enabled,
            self.score.light_years.hex(),
            self.coins_collected,
            self._shoot_cooldown.hex(),
            tuple(entity.state_key() for entity in self.entities),
            tuple(formation.state_key() for formation in self.formations),
            tuple(projectile.state_key() for projectile in self.projectiles),
            self.spawner.state_key(),
            self.coin_spawner.state_key(),
            self._director_rng.getstate(),
            self.difficulty,
        )
        if isinstance(self.director, StatefulDirector):
            return (*state, self.director.state_key())
        return state

    def state_hash(self) -> str:
        """SHA-256 über `state_key()` — beweist Gleichheit zweier Läufe."""
        return hashlib.sha256(repr(self.state_key()).encode("utf-8")).hexdigest()

    # --- Schritt --------------------------------------------------------------

    def step(self, inputs: InputFrame) -> list[SimEvent]:
        """Ein fester Zeitschritt. Nach dem Tod ein No-op."""
        if self.is_over:
            return []
        dt = SIM_DT
        events: list[SimEvent] = []
        self.tick += 1
        self.difficulty = self.director.params(self, self._director_rng)
        speed = self.difficulty.speed_multiplier
        interval = self.difficulty.spawn_interval_multiplier

        self.player.update(dt, inputs)
        self.score.set_rate_multiplier(speed)
        self.score.update(dt)
        if InputFrame.SWAP_WEAPON in inputs:
            self.loadout.cycle_weapon()
        self._update_shooting(dt, inputs, events)

        self.entities.extend(
            self.spawner.update(dt, accept=self._accept_entity, interval_scale=interval)
        )
        player_y = self.player.rect.centery
        for entity in self.entities:
            entity.update(dt, player_y, speed)
        self.entities = [entity for entity in self.entities if not entity.is_off_screen]

        for projectile in self.projectiles:
            projectile.update(dt)
        self.projectiles = [p for p in self.projectiles if not p.is_off_screen]

        collected = collect_pickups(self.player, self.entities)
        if collected:
            self.loadout.refill_standard()
            events.extend(
                self._event(EventKind.AMMO_PICKUP, position=pickup.rect.center)
                for pickup in collected
            )

        self._update_coins(dt, player_y, speed, events)

        for impact in resolve_projectile_hits(self.projectiles, self.entities):
            events.append(self._event(EventKind.HIT, position=impact.position))
            if impact.destroyed:
                events.append(self._event(EventKind.DESTROYED, position=impact.position))

        if self.shield_charges > 0 and absorb_contact(self.player, self.entities):
            self.shield_charges -= 1
            events.append(self._event(EventKind.SHIELD))
        else:
            hp_before = self.player.hp
            self.player.hp = apply_contact_damage(self.player, self.player.hp, self.entities)
            if self.player.hp != hp_before:
                events.append(self._event(EventKind.CONTACT, value=hp_before - self.player.hp))
        if self.player.hp <= 0:
            self.is_over = True
            events.append(self._event(EventKind.DEATH))
        return events

    def _event(
        self,
        kind: EventKind,
        *,
        value: int = 0,
        sound: str | None = None,
        position: tuple[int, int] | None = None,
    ) -> SimEvent:
        """Baut ein `SimEvent` mit dem Snapshot des aktuellen Zustands.

        Ohne `position` gilt die Schiffsmitte — dort passieren Pickups,
        Schildtreffer und Kollisionen ohnehin.
        """
        anchor = position if position is not None else self.player.rect.center
        return SimEvent(kind, self.snapshot(), value, sound, anchor)

    def _update_shooting(self, dt: float, inputs: InputFrame, events: list[SimEvent]) -> None:
        """Feuert bei `FIRE`, wenn Cooldown abgelaufen und Munition vorhanden ist."""
        self._shoot_cooldown = max(0.0, self._shoot_cooldown - dt)
        if InputFrame.FIRE not in inputs or self._shoot_cooldown > 0.0:
            return
        fired_spec = self.loadout.active.spec
        if not self.loadout.fire():
            return
        projectile = spawn_projectile(self.player, damage=fired_spec.damage)
        self.projectiles.append(projectile)
        self._shoot_cooldown = fired_spec.fire_cooldown
        events.append(
            self._event(
                EventKind.FIRED,
                value=fired_spec.damage,
                sound=fired_spec.sound,
                position=projectile.rect.center,
            )
        )

    def _hazard_rects(self) -> list[object]:
        """Hitboxen aller Entities, die dem Spieler schaden."""
        return [entity.rect for entity in self.entities if entity.damages_player]

    def _accept_entity(self, entity: Entity) -> bool:
        """Gefahren spawnen nicht in ein Münz-Muster: gleich schnell → sonst dauerhaft verdeckt."""
        if not entity.damages_player:
            return True
        return is_clear([entity.rect], coin_rects(self.formations), COIN_HAZARD_CLEARANCE)

    def _accept_formation(self, formation: CoinFormation) -> bool:
        """Gegenstück zu `_accept_entity`: kein Münz-Muster in eine Gefahr hinein."""
        hazards = [entity.rect for entity in self.entities if entity.damages_player]
        return is_clear(coin_rects([formation]), hazards, COIN_HAZARD_CLEARANCE)

    def _update_coins(
        self,
        dt: float,
        player_y: int,
        speed: float,
        events: list[SimEvent],
    ) -> None:
        """Spawnt, bewegt und sammelt Münz-Formationen; Magnet zieht im Radius heran.

        Münzwert und Bonus erhöhen `coins_collected` und liefern je ein Event.
        Die zeitliche Kadenz folgt dem Welttempo, nicht der Gefahren-Dichte.
        """
        # Die Gefahren-Dichte darf keine zusätzliche Münzdichte erzeugen.
        # Nur das höhere Welttempo verkürzt die Zeitabstände, sodass der
        # räumliche Abstand der Formationen ungefähr konstant bleibt.
        coin_interval = 1.0 / speed
        self.formations.extend(
            self.coin_spawner.update(
                dt,
                accept=self._accept_formation,
                interval_scale=coin_interval,
            )
        )
        for formation in self.formations:
            formation.update(dt, player_y, speed)
            if self.magnet_enabled:
                formation.attract(self.player.rect.center, MAGNET_RADIUS, MAGNET_PULL_SPEED * dt)
            pickup = formation.collect(self.player)
            if pickup.coins:
                self.coins_collected += pickup.coins
                events.append(self._event(EventKind.COIN, value=pickup.coins))
            if pickup.bonus:
                self.coins_collected += pickup.bonus
                events.append(self._event(EventKind.COIN_BONUS, value=pickup.bonus))
        self.formations = [f for f in self.formations if not f.is_finished]
