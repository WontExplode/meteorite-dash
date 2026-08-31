"""Treffer-Feedback fürs Spiel: Funken, Explosionen, Blitze und Erschütterung.

Reines Rendering wie `starfield.py` und `menu_fx.py`: Wandzeit, ungeseedeter
Zufall, Referenzraum, Zeichnen über den `RenderContext`. Nichts davon berührt
die Simulation — Replays und Hashes bleiben unverändert.

`GameScene` löst die Effekte aus den `SimEvent`s aus; die Erschütterung kommt
als `offset` zurück und wandert in den `RenderContext`, damit die Welt wackelt
und das HUD ruhig bleibt.
"""

import math
from dataclasses import dataclass
from random import Random

import pygame

from meteorite_dash.config import (
    DAMAGE_FLASH_ALPHA,
    DAMAGE_FLASH_COLOR,
    DAMAGE_FLASH_SECONDS,
    DEATH_FLASH_ALPHA,
    DEATH_FLASH_COLOR,
    DEATH_FLASH_SECONDS,
    EXPLOSION_COLORS,
    EXPLOSION_COUNT,
    EXPLOSION_RADIUS,
    EXPLOSION_TTL,
    FEEDBACK_DRAG,
    FEEDBACK_MAX_PARTICLES,
    FEEDBACK_PARTICLE_SPEED,
    HIT_SPARK_COLOR,
    HIT_SPARK_COUNT,
    HIT_SPARK_RADIUS,
    HIT_SPARK_TTL,
    PICKUP_SPARK_COUNT,
    PICKUP_SPARK_RADIUS,
    PICKUP_SPARK_TTL,
    SHAKE_CONTACT,
    SHAKE_DEATH,
    SHAKE_DESTROY,
    SHIELD_FLASH_ALPHA,
    SHIELD_FLASH_COLOR,
    SHIELD_FLASH_SECONDS,
    Color,
)
from meteorite_dash.render import RenderContext

_MAX_DT = 0.05  # Deckel gegen Riesen-Frames (Fenster verschoben o. Ä.)
_SHIELD_RING_RADIUS = 46.0  # Referenz-px; wächst über die Blitzdauer


@dataclass
class Particle:
    """Kurzlebiger Funke im Referenzraum; schrumpft mit ablaufender Lebenszeit."""

    x: float
    y: float
    vel_x: float
    vel_y: float
    ttl: float
    max_ttl: float
    radius: float
    color: Color


class Effects:
    """Deko-Schicht der Spielszene: Partikel, Vollbild-Blitz und Erschütterung.

    Die semantischen Methoden (`hit`, `explosion`, …) bündeln die Werte aus
    `config.py`, damit die Szene nur noch sagen muss, *was* passiert ist.
    """

    def __init__(self, rng: Random | None = None) -> None:
        self.random = rng if rng is not None else Random()
        self.particles: list[Particle] = []
        self._flash_color: Color = DAMAGE_FLASH_COLOR
        self._flash_alpha = 0
        self._flash_ttl = 0.0
        self._flash_max_ttl = 1.0
        self._shake_strength = 0.0
        self._shake_ttl = 0.0
        self._shake_max_ttl = 1.0
        self._offset = (0.0, 0.0)
        self._ring: tuple[float, float, float, Color] | None = None  # x, y, ttl, Farbe
        self._ring_max_ttl = 1.0
        self._overlay: pygame.Surface | None = None

    # --- Auslöser ----------------------------------------------------------

    def hit(self, position: tuple[int, int]) -> None:
        """Projektil schlägt ein: wenige helle Funken."""
        self._burst(position, HIT_SPARK_COUNT, HIT_SPARK_TTL, HIT_SPARK_RADIUS, (HIT_SPARK_COLOR,))

    def explosion(self, position: tuple[int, int]) -> None:
        """Ziel zerbricht: Trümmerwolke in Feuerfarben plus kurzer Ruck."""
        self._burst(position, EXPLOSION_COUNT, EXPLOSION_TTL, EXPLOSION_RADIUS, EXPLOSION_COLORS)
        self.shake(*SHAKE_DESTROY)

    def pickup(self, position: tuple[int, int], color: Color) -> None:
        """Münze oder Munition eingesammelt: Funken in der Farbe des Aufsammelten."""
        self._burst(position, PICKUP_SPARK_COUNT, PICKUP_SPARK_TTL, PICKUP_SPARK_RADIUS, (color,))

    def damage(self, position: tuple[int, int]) -> None:
        """Kollision am Schiff: roter Blitz, Ruck und Trümmer."""
        self._burst(position, EXPLOSION_COUNT, EXPLOSION_TTL, EXPLOSION_RADIUS, EXPLOSION_COLORS)
        self.flash(DAMAGE_FLASH_COLOR, DAMAGE_FLASH_SECONDS, DAMAGE_FLASH_ALPHA)
        self.shake(*SHAKE_CONTACT)

    def shield(self, position: tuple[int, int]) -> None:
        """Schild blockt: blauer Ring um das Schiff und kurzer Blitz."""
        self.flash(SHIELD_FLASH_COLOR, SHIELD_FLASH_SECONDS, SHIELD_FLASH_ALPHA)
        self._ring = (
            float(position[0]),
            float(position[1]),
            SHIELD_FLASH_SECONDS,
            SHIELD_FLASH_COLOR,
        )
        self._ring_max_ttl = SHIELD_FLASH_SECONDS

    def death(self, position: tuple[int, int]) -> None:
        """Schiff zerstört: große Explosion, langer Blitz, kräftiger Ruck."""
        for _ in range(3):
            self._burst(
                position, EXPLOSION_COUNT, EXPLOSION_TTL, EXPLOSION_RADIUS, EXPLOSION_COLORS
            )
        self.flash(DEATH_FLASH_COLOR, DEATH_FLASH_SECONDS, DEATH_FLASH_ALPHA)
        self.shake(*SHAKE_DEATH)

    def flash(self, color: Color, seconds: float, alpha: int) -> None:
        """Legt einen ausblendenden Farbschleier über das Bild (der letzte gewinnt)."""
        self._flash_color = color
        self._flash_alpha = alpha
        self._flash_ttl = seconds
        self._flash_max_ttl = seconds

    def shake(self, strength: float, seconds: float) -> None:
        """Erschüttert die Welt; ein stärkerer Ruck überschreibt einen laufenden."""
        if strength * seconds < self._shake_strength * self._shake_ttl:
            return
        self._shake_strength = strength
        self._shake_ttl = seconds
        self._shake_max_ttl = seconds

    # --- Update & Zeichnen -------------------------------------------------

    @property
    def offset(self) -> tuple[float, float]:
        """Aktueller Erschütterungs-Versatz in Referenz-px für den `RenderContext`."""
        return self._offset

    def update(self, dt: float) -> None:
        """Rückt Partikel, Blitz, Ring und Erschütterung um `dt` Wandzeit vor."""
        dt = min(dt, _MAX_DT)
        self._update_particles(dt)
        self._flash_ttl = max(0.0, self._flash_ttl - dt)
        if self._ring is not None:
            x, y, ttl, color = self._ring
            ttl -= dt
            self._ring = None if ttl <= 0 else (x, y, ttl, color)
        self._update_shake(dt)

    def _update_particles(self, dt: float) -> None:
        remaining: list[Particle] = []
        damping = math.exp(-FEEDBACK_DRAG * dt)
        for particle in self.particles:
            particle.ttl -= dt
            if particle.ttl <= 0:
                continue
            particle.x += particle.vel_x * dt
            particle.y += particle.vel_y * dt
            particle.vel_x *= damping
            particle.vel_y *= damping
            remaining.append(particle)
        self.particles = remaining

    def _update_shake(self, dt: float) -> None:
        self._shake_ttl = max(0.0, self._shake_ttl - dt)
        if self._shake_ttl <= 0:
            self._offset = (0.0, 0.0)
            return
        fade = self._shake_ttl / self._shake_max_ttl
        amplitude = self._shake_strength * fade
        self._offset = (
            self.random.uniform(-amplitude, amplitude),
            self.random.uniform(-amplitude, amplitude),
        )

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet Partikel und den Schildring in der Welt (folgt der Erschütterung)."""
        vp = ctx.viewport
        for particle in self.particles:
            fade = particle.ttl / particle.max_ttl
            radius = max(1, vp.s(particle.radius * fade))
            pygame.draw.circle(
                ctx.surface, particle.color, ctx.point(particle.x, particle.y), radius
            )
        if self._ring is not None:
            x, y, ttl, color = self._ring
            grow = 1.0 - ttl / self._ring_max_ttl
            radius = max(1, vp.s(_SHIELD_RING_RADIUS * (0.4 + grow)))
            width = max(1, vp.s(3 * (1.0 - grow)))
            pygame.draw.circle(ctx.surface, color, ctx.point(x, y), radius, width)

    def draw_overlay(self, surface: pygame.Surface) -> None:
        """Legt den Vollbild-Blitz über das fertige Bild (unter dem HUD)."""
        if self._flash_ttl <= 0:
            return
        overlay = self._overlay_surface(surface.get_size())
        overlay.fill(self._flash_color)
        overlay.set_alpha(round(self._flash_alpha * self._flash_ttl / self._flash_max_ttl))
        surface.blit(overlay, (0, 0))

    def _overlay_surface(self, size: tuple[int, int]) -> pygame.Surface:
        """Blitz-Fläche in Fenstergröße; wird nach einem Resize neu gebaut."""
        if self._overlay is None or self._overlay.get_size() != size:
            self._overlay = pygame.Surface(size)
        return self._overlay

    # --- Partikel ----------------------------------------------------------

    def _burst(
        self,
        position: tuple[int, int],
        count_range: tuple[int, int],
        ttl_range: tuple[float, float],
        radius: float,
        palette: tuple[Color, ...],
    ) -> None:
        """Streut Funken in alle Richtungen; die Farbe kommt aus der Palette."""
        budget = FEEDBACK_MAX_PARTICLES - len(self.particles)
        for _ in range(min(self.random.randint(*count_range), max(0, budget))):
            direction = self.random.uniform(0.0, 2 * math.pi)
            speed = self.random.uniform(*FEEDBACK_PARTICLE_SPEED)
            ttl = self.random.uniform(*ttl_range)
            self.particles.append(
                Particle(
                    x=float(position[0]),
                    y=float(position[1]),
                    vel_x=math.cos(direction) * speed,
                    vel_y=math.sin(direction) * speed,
                    ttl=ttl,
                    max_ttl=ttl,
                    radius=radius,
                    color=self.random.choice(palette),
                )
            )
