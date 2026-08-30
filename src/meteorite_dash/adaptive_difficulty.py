"""Adaptiver Schwierigkeits-Director für den freien Infinite-Scroller.

Der Director bewertet ausschließlich den festen Simulationszustand pro Tick.
Dadurch fühlt sich jeder zufällig gestartete Free Run anders an, bleibt mit
demselben Seed und denselben Eingaben aber für Tests und Replays reproduzierbar.
"""

import random
from dataclasses import dataclass

import pygame

from meteorite_dash.config import (
    DIFFICULTY_AMMO_RELIEF_MAX,
    DIFFICULTY_COMFORT_MASTERY_PER_SECOND,
    DIFFICULTY_COMFORT_STREAK_SECONDS,
    DIFFICULTY_DAMAGE_HOLD_SECONDS,
    DIFFICULTY_DAMAGE_MASTERY_LOSS,
    DIFFICULTY_DAMAGE_STRESS_GAIN,
    DIFFICULTY_FALL_PER_SECOND,
    DIFFICULTY_LOW_HP_INTENSITY_CAP,
    DIFFICULTY_LOW_HP_RATIO,
    DIFFICULTY_NEAR_MISS_COMBO_CAP,
    DIFFICULTY_NEAR_MISS_MARGIN,
    DIFFICULTY_NEAR_MISS_STRESS_GAIN,
    DIFFICULTY_NEAR_MISS_WINDOW_SECONDS,
    DIFFICULTY_PROBE_SECONDS,
    DIFFICULTY_RISE_PER_SECOND_MAX,
    DIFFICULTY_RISE_PER_SECOND_MIN,
    DIFFICULTY_SAFE_PASS_MASTERY_GAIN,
    DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_MIN,
    DIFFICULTY_SPEED_MULTIPLIER_MAX,
    DIFFICULTY_START_GRACE_SECONDS,
    DIFFICULTY_STRESS_DECAY_PER_SECOND,
    DIFFICULTY_SURVIVAL_MASTERY_PER_SECOND,
    DIFFICULTY_TIME_PROBE_MAX,
    SIM_TICKS_PER_SECOND,
)
from meteorite_dash.difficulty import DifficultyParams, SimulationView
from meteorite_dash.entities import Entity


@dataclass(frozen=True)
class DifficultyDiagnostics:
    """Lesbarer Zustand für Tests und das spätere optionale Debug-HUD."""

    intensity: float
    target_intensity: float
    mastery: float
    stress: float
    safe_passes: int
    near_misses: int
    damage_free_ticks: int
    hold_until_tick: int


@dataclass
class _TrackedEntity:
    serial: int
    evaluated: bool = False


class AdaptiveDirector:
    """Regelt den Free Mode nahe an die beobachtete Leistungsgrenze.

    Sichere Passagen und schadensfreies Spielen erhöhen die Kompetenzschätzung.
    Schaden und gehäufte Beinahe-Kollisionen erzeugen kurzfristigen Stress und
    senken die tatsächliche Intensität deutlich schneller, als sie ansteigt.
    """

    def __init__(self) -> None:
        self._intensity = 0.0
        self._target_intensity = 0.0
        self._mastery = 0.0
        self._stress = 0.0
        self._last_tick = 0
        self._last_hp: int | None = None
        self._damage_free_ticks = 0
        self._hold_until_tick = 0
        self._near_miss_ticks: list[int] = []
        self._safe_passes = 0
        self._near_misses = 0
        self._next_entity_id = 0
        self._tracked: dict[Entity, _TrackedEntity] = {}
        self._last_params = DifficultyParams()

    @property
    def diagnostics(self) -> DifficultyDiagnostics:
        return DifficultyDiagnostics(
            intensity=self._intensity,
            target_intensity=self._target_intensity,
            mastery=self._mastery,
            stress=self._stress,
            safe_passes=self._safe_passes,
            near_misses=self._near_misses,
            damage_free_ticks=self._damage_free_ticks,
            hold_until_tick=self._hold_until_tick,
        )

    def params(self, sim: SimulationView, rng: random.Random) -> DifficultyParams:
        """Bewertet einen Simulationstick; `rng` bleibt für spätere Events reserviert."""
        if sim.tick <= self._last_tick:
            return self._last_params

        elapsed_ticks = sim.tick - self._last_tick
        elapsed_seconds = elapsed_ticks / SIM_TICKS_PER_SECOND
        self._last_tick = sim.tick

        self._decay_stress(elapsed_seconds)
        self._observe_damage(sim, elapsed_ticks)
        has_active_hazard = self._observe_entities(sim)
        self._learn_from_survival(elapsed_seconds, has_active_hazard)
        self._update_target(sim)
        self._move_toward_target(elapsed_seconds)
        self._last_params = self._map_params()
        return self._last_params

    def state_key(self) -> tuple[object, ...]:
        """Kanonischer interner Zustand für den späteren Simulationshash."""
        tracked = tuple(
            (state.serial, state.evaluated, entity.state_key())
            for entity, state in sorted(self._tracked.items(), key=lambda item: item[1].serial)
        )
        return (
            "adaptive-v1",
            self._intensity.hex(),
            self._target_intensity.hex(),
            self._mastery.hex(),
            self._stress.hex(),
            self._last_tick,
            self._last_hp,
            self._damage_free_ticks,
            self._hold_until_tick,
            tuple(self._near_miss_ticks),
            self._safe_passes,
            self._near_misses,
            self._next_entity_id,
            tracked,
            self._last_params,
        )

    def _decay_stress(self, elapsed_seconds: float) -> None:
        self._stress = max(
            0.0,
            self._stress - DIFFICULTY_STRESS_DECAY_PER_SECOND * elapsed_seconds,
        )

    def _observe_damage(self, sim: SimulationView, elapsed_ticks: int) -> None:
        hp = sim.player.hp
        if self._last_hp is None:
            self._last_hp = hp
            self._damage_free_ticks = elapsed_ticks
            return

        damage = max(0, self._last_hp - hp)
        self._last_hp = hp
        if damage == 0:
            self._damage_free_ticks += elapsed_ticks
            return

        damage_ratio = damage / max(1, sim.player.max_hp)
        self._mastery = _clamp01(self._mastery - damage_ratio * DIFFICULTY_DAMAGE_MASTERY_LOSS)
        self._stress = _clamp01(self._stress + damage_ratio * DIFFICULTY_DAMAGE_STRESS_GAIN)
        self._damage_free_ticks = 0
        hold_ticks = round(DIFFICULTY_DAMAGE_HOLD_SECONDS * SIM_TICKS_PER_SECOND)
        self._hold_until_tick = max(self._hold_until_tick, sim.tick + hold_ticks)

    def _observe_entities(self, sim: SimulationView) -> bool:
        self._tracked = {
            entity: state for entity, state in self._tracked.items() if entity in sim.entities
        }

        player_rect = sim.player.rect
        has_active_hazard = False
        for entity in sim.entities:
            if not entity.damages_player:
                continue
            state = self._tracked.get(entity)
            if state is None:
                state = _TrackedEntity(self._next_entity_id)
                self._next_entity_id += 1
                self._tracked[entity] = state

            if entity.rect.right >= player_rect.left:
                has_active_hazard = True
                continue
            if state.evaluated:
                continue

            state.evaluated = True
            if _vertical_gap(player_rect, entity.rect) <= DIFFICULTY_NEAR_MISS_MARGIN:
                self._record_near_miss(sim.tick)
            else:
                self._safe_passes += 1
                self._mastery = _clamp01(self._mastery + DIFFICULTY_SAFE_PASS_MASTERY_GAIN)
        return has_active_hazard

    def _record_near_miss(self, tick: int) -> None:
        window_ticks = round(DIFFICULTY_NEAR_MISS_WINDOW_SECONDS * SIM_TICKS_PER_SECOND)
        first_tick = tick - window_ticks
        self._near_miss_ticks = [
            near_tick for near_tick in self._near_miss_ticks if near_tick >= first_tick
        ]
        self._near_miss_ticks.append(tick)
        combo = min(len(self._near_miss_ticks), DIFFICULTY_NEAR_MISS_COMBO_CAP)
        self._near_misses += 1
        self._stress = _clamp01(self._stress + DIFFICULTY_NEAR_MISS_STRESS_GAIN * combo)

    def _learn_from_survival(self, elapsed_seconds: float, has_active_hazard: bool) -> None:
        if not has_active_hazard:
            return
        gain = DIFFICULTY_SURVIVAL_MASTERY_PER_SECOND
        comfort_ticks = round(DIFFICULTY_COMFORT_STREAK_SECONDS * SIM_TICKS_PER_SECOND)
        if self._damage_free_ticks >= comfort_ticks:
            gain += DIFFICULTY_COMFORT_MASTERY_PER_SECOND
        self._mastery = _clamp01(self._mastery + gain * elapsed_seconds)

    def _update_target(self, sim: SimulationView) -> None:
        probe_ticks = max(1, round(DIFFICULTY_PROBE_SECONDS * SIM_TICKS_PER_SECOND))
        time_probe = min(1.0, sim.tick / probe_ticks) * DIFFICULTY_TIME_PROBE_MAX

        standard = sim.loadout.weapons[0]
        ammo_ratio = standard.ammo / max(1, standard.spec.max_ammo)
        ammo_relief = (1.0 - ammo_ratio) ** 2 * DIFFICULTY_AMMO_RELIEF_MAX

        target = _clamp01(self._mastery + time_probe - self._stress - ammo_relief)
        grace_ticks = round(DIFFICULTY_START_GRACE_SECONDS * SIM_TICKS_PER_SECOND)
        if sim.tick <= grace_ticks:
            target = 0.0
        if sim.tick < self._hold_until_tick:
            target = min(target, self._intensity)

        hp_ratio = sim.player.hp / max(1, sim.player.max_hp)
        if hp_ratio <= DIFFICULTY_LOW_HP_RATIO:
            target = min(target, DIFFICULTY_LOW_HP_INTENSITY_CAP)
        self._target_intensity = target

    def _move_toward_target(self, elapsed_seconds: float) -> None:
        if self._target_intensity >= self._intensity:
            rise_range = DIFFICULTY_RISE_PER_SECOND_MAX - DIFFICULTY_RISE_PER_SECOND_MIN
            rate = DIFFICULTY_RISE_PER_SECOND_MIN + rise_range * self._mastery
        else:
            rate = DIFFICULTY_FALL_PER_SECOND

        distance = self._target_intensity - self._intensity
        step = min(abs(distance), rate * elapsed_seconds)
        self._intensity = _clamp01(
            self._intensity + step if distance >= 0 else self._intensity - step
        )

    def _map_params(self) -> DifficultyParams:
        speed_range = DIFFICULTY_SPEED_MULTIPLIER_MAX - 1.0
        interval_range = 1.0 - DIFFICULTY_SPAWN_INTERVAL_MULTIPLIER_MIN
        return DifficultyParams(
            speed_multiplier=1.0 + speed_range * self._intensity,
            spawn_interval_multiplier=1.0 - interval_range * self._intensity,
        )


def _vertical_gap(first: pygame.Rect, second: pygame.Rect) -> int:
    if first.bottom < second.top:
        return second.top - first.bottom
    if second.bottom < first.top:
        return first.top - second.bottom
    return 0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))
