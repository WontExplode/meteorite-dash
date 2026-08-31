"""Eye-Candy fürs Hauptmenü: Meteoriten, Deko-Gegner, Projektile und Funken.

Reines Rendering wie `starfield.py`: rechnet im Referenzraum, nutzt
ungeseedeten Zufall und Wandzeit. Gehört nicht zur Simulation und beeinflusst
weder Replays noch Hashes — hier gelten die Sim-Regeln (Seed-Streams,
`det_sin`) bewusst nicht.
"""

import math
from dataclasses import dataclass
from random import Random

import pygame

from meteorite_dash.config import (
    ENEMY_SIZE,
    HUNTER_ENEMY_COLOR,
    METEORITE_COLOR,
    METEORITE_VARIANTS,
    PROJECTILE_COLOR,
    PROJECTILE_SIZE,
    REFERENCE_SIZE,
    WAVE_ENEMY_COLOR,
    Color,
)
from meteorite_dash.render import RenderContext

# Deko-Tuning, bewusst lokal wie im `StarField` (kein Spielwert, nur Optik).
_MAX_METEORITES = 7
_SPAWN_INTERVAL = (0.6, 1.5)  # Sekunden zwischen Meteoriten-Spawns
_METEORITE_SPEED = (70.0, 150.0)  # Referenz-px/s nach links
_METEORITE_DRIFT = (-35.0, 35.0)  # vertikale Startgeschwindigkeit
_METEORITE_SPIN = (-100.0, 100.0)  # Grad/s Eigenrotation
_BOUNCE_DAMPING = 0.75  # Geschwindigkeitsverlust beim Abprallen
_BOUNCE_MIN_KICK = 30.0  # Mindesttempo weg vom Ziel nach dem Abprall
_IMPULSE_FACTOR = 0.4  # Anteil der Meteoriten-Geschwindigkeit, der das Ziel anstößt
_SPRING_STIFFNESS = 90.0  # Feder-Rückstellung der angestoßenen Ziele
_SPRING_DAMPING = 7.0
_ANGLE_BUCKET_DEG = 6  # Rotations-Cache-Raster (Grad)
_ROTATION_CACHE_MAX = 720

_ENEMY_ANCHORS = ((70.0, 150.0), (110.0, 450.0))  # Patrouillen-Anker links (Spielerseite)
_ENEMY_COLORS: tuple[Color, Color] = (WAVE_ENEMY_COLOR, HUNTER_ENEMY_COLOR)
_ENEMY_SWAY_X = 20.0  # horizontales Pendeln um den Anker
_ENEMY_IDLE_AMPLITUDE = 70.0  # vertikales Pendeln ohne Ziel
_ENEMY_HUNT_SPEED = 110.0  # Referenz-px/s Richtung Ziel-Höhe
_ENEMY_ALIGN_TOLERANCE = 26.0  # Höhen-Toleranz, ab der geschossen wird
_ENEMY_COOLDOWN = (1.6, 3.0)  # Sekunden zwischen Schüssen
_ENEMY_MARGIN_Y = 20.0  # Abstand zu oberem/unterem Rand

_ENEMY_AIM_JITTER = 26.0  # Streuung der Schüsse — Fehlschüsse sind gewollt
_FX_PROJECTILE_SPEED = 430.0  # Referenz-px/s nach rechts
_PROJECTILE_END_X = 770.0  # rechts davon verglüht das Projektil

_DEBRIS_COUNT = (6, 10)
_SPARK_COUNT = (3, 5)
_PARTICLE_SPEED = (40.0, 170.0)
_DEBRIS_TTL = (0.35, 0.8)
_SPARK_TTL = (0.2, 0.45)
_DEBRIS_RADIUS = 3.0
_SPARK_RADIUS = 2.0
_SPARK_COLOR: Color = (255, 240, 180)

_MAX_DT = 0.05  # Deckel gegen Riesen-Frames (Fenster verschoben o. Ä.)


@dataclass
class MenuTarget:
    """Abpraller-Ziel (Titel/Menüpunkt) mit gedämpfter Feder-Rückstellung."""

    rect: pygame.Rect
    offset_x: float = 0.0
    offset_y: float = 0.0
    vel_x: float = 0.0
    vel_y: float = 0.0

    @property
    def offset(self) -> tuple[float, float]:
        """Aktuelle Auslenkung in Referenz-px; die Szene addiert sie beim Zeichnen."""
        return (self.offset_x, self.offset_y)

    def hitbox(self) -> pygame.Rect:
        """Kollisionsrechteck inklusive aktueller Auslenkung."""
        return self.rect.move(round(self.offset_x), round(self.offset_y))

    def kick(self, vel_x: float, vel_y: float) -> None:
        """Stößt das Ziel an; die Feder holt es zurück."""
        self.vel_x += vel_x
        self.vel_y += vel_y

    def update(self, dt: float) -> None:
        """Gedämpfte Feder (semi-implizites Euler) zurück in die Ruhelage."""
        self.vel_x += (-_SPRING_STIFFNESS * self.offset_x - _SPRING_DAMPING * self.vel_x) * dt
        self.vel_y += (-_SPRING_STIFFNESS * self.offset_y - _SPRING_DAMPING * self.vel_y) * dt
        self.offset_x += self.vel_x * dt
        self.offset_y += self.vel_y * dt


@dataclass
class FxMeteorite:
    """Deko-Meteorit; Position ist der Mittelpunkt im Referenzraum."""

    x: float
    y: float
    vel_x: float
    vel_y: float
    diameter: int
    image_name: str
    angle: float
    spin: float

    @property
    def rect(self) -> pygame.Rect:
        """Hitbox (Referenzraum), zentriert auf die Float-Position."""
        rect = pygame.Rect(0, 0, self.diameter, self.diameter)
        rect.center = (round(self.x), round(self.y))
        return rect


@dataclass
class FxEnemy:
    """Deko-Gegner: pendelt um seinen Anker und schießt auf Meteoriten."""

    anchor_x: float
    base_y: float
    phase: float
    color: Color
    x: float
    y: float
    cooldown: float

    @property
    def rect(self) -> pygame.Rect:
        """Zeichenrechteck in `ENEMY_SIZE`, zentriert auf die Position."""
        rect = pygame.Rect(0, 0, *ENEMY_SIZE)
        rect.center = (round(self.x), round(self.y))
        return rect


@dataclass
class FxProjectile:
    """Deko-Projektil eines Gegners, fliegt nach rechts."""

    x: float
    y: float
    vel_x: float

    @property
    def rect(self) -> pygame.Rect:
        """Hitbox in `PROJECTILE_SIZE`, vertikal zentriert."""
        width, height = PROJECTILE_SIZE
        return pygame.Rect(round(self.x), round(self.y - height / 2), width, height)


@dataclass
class FxParticle:
    """Kurzlebiger Funke/Trümmer; schrumpft mit ablaufender Lebenszeit."""

    x: float
    y: float
    vel_x: float
    vel_y: float
    ttl: float
    max_ttl: float
    radius: float
    color: Color


class MenuFX:
    """Deko-Schicht des Hauptmenüs.

    Meteoriten treiben von rechts herein und prallen von den übergebenen
    Ziel-Rechtecken (Titel, Menüpunkte) ab; zwei Gegner patrouillieren auf
    der Spielerseite links und schießen Meteoriten ab. Alles rechnet im Referenzraum
    und wird über den `RenderContext` gezeichnet.
    """

    def __init__(self, targets: list[pygame.Rect], rng: Random | None = None) -> None:
        self.random = rng if rng is not None else Random()
        self.targets = [MenuTarget(rect) for rect in targets]
        self.meteorites: list[FxMeteorite] = []
        self.projectiles: list[FxProjectile] = []
        self.particles: list[FxParticle] = []
        self.enemies = [
            FxEnemy(
                anchor_x=anchor_x,
                base_y=base_y,
                phase=index * 2.1,
                color=_ENEMY_COLORS[index % len(_ENEMY_COLORS)],
                x=anchor_x,
                y=base_y,
                cooldown=self.random.uniform(*_ENEMY_COOLDOWN),
            )
            for index, (anchor_x, base_y) in enumerate(_ENEMY_ANCHORS)
        ]
        self._elapsed = 0.0
        self._spawn_timer = self.random.uniform(*_SPAWN_INTERVAL)
        self._rotation_cache: dict[tuple[str, int, int], pygame.Surface] = {}

    # --- Update ------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Rückt die Deko um `dt` Sekunden Wandzeit vor."""
        dt = min(dt, _MAX_DT)
        self._elapsed += dt
        self._spawn(dt)
        self._update_meteorites(dt)
        for enemy in self.enemies:
            self._update_enemy(enemy, dt)
        self._update_projectiles(dt)
        self._update_particles(dt)
        for target in self.targets:
            target.update(dt)

    def _spawn(self, dt: float) -> None:
        """Würfelt timergesteuert neue Meteoriten am rechten Rand."""
        self._spawn_timer -= dt
        if self._spawn_timer > 0 or len(self.meteorites) >= _MAX_METEORITES:
            return
        self._spawn_timer = self.random.uniform(*_SPAWN_INTERVAL)
        # Nur Tiny/Small/Medium: Large würde die Menütexte erschlagen.
        variant = self.random.choices(METEORITE_VARIANTS[:3], weights=(4, 3, 2))[0]
        diameter = variant.radius * 2
        self.meteorites.append(
            FxMeteorite(
                x=REFERENCE_SIZE[0] + diameter,
                y=self.random.uniform(_ENEMY_MARGIN_Y, REFERENCE_SIZE[1] - 80),
                vel_x=-self.random.uniform(*_METEORITE_SPEED),
                vel_y=self.random.uniform(*_METEORITE_DRIFT),
                diameter=diameter,
                image_name=self.random.choice(variant.images),
                angle=self.random.uniform(0.0, 360.0),
                spin=self.random.uniform(*_METEORITE_SPIN),
            )
        )

    def _update_meteorites(self, dt: float) -> None:
        """Bewegt, dreht und prallt Meteoriten ab; entfernt entkommene."""
        remaining: list[FxMeteorite] = []
        for meteorite in self.meteorites:
            meteorite.x += meteorite.vel_x * dt
            meteorite.y += meteorite.vel_y * dt
            meteorite.angle = (meteorite.angle + meteorite.spin * dt) % 360.0
            self._bounce_screen_edges(meteorite)
            for target in self.targets:
                if meteorite.rect.colliderect(target.hitbox()):
                    self._bounce_off_target(meteorite, target)
                    break
            radius = meteorite.diameter / 2
            escaped_left = meteorite.x < -radius - 40
            escaped_right = meteorite.vel_x > 0 and meteorite.x - radius > REFERENCE_SIZE[0]
            if not escaped_left and not escaped_right:
                remaining.append(meteorite)
        self.meteorites = remaining

    def _bounce_screen_edges(self, meteorite: FxMeteorite) -> None:
        """Hält Meteoriten über oben/unten im Bild (Reflexion an den Rändern)."""
        radius = meteorite.diameter / 2
        if meteorite.y - radius < 0 and meteorite.vel_y < 0:
            meteorite.vel_y = abs(meteorite.vel_y)
        elif meteorite.y + radius > REFERENCE_SIZE[1] and meteorite.vel_y > 0:
            meteorite.vel_y = -abs(meteorite.vel_y)

    def _bounce_off_target(self, meteorite: FxMeteorite, target: MenuTarget) -> None:
        """Reflexion an der Achse mit der kleinsten Überlappung, Ziel bekommt den Impuls."""
        rect = meteorite.rect
        hit = target.hitbox()
        overlap_x = min(rect.right - hit.left, hit.right - rect.left)
        overlap_y = min(rect.bottom - hit.top, hit.bottom - rect.top)
        impact_x, impact_y = meteorite.vel_x, meteorite.vel_y
        if overlap_x < overlap_y:
            bounced = max(abs(meteorite.vel_x) * _BOUNCE_DAMPING, _BOUNCE_MIN_KICK)
            if rect.centerx < hit.centerx:
                meteorite.x -= overlap_x
                meteorite.vel_x = -bounced
            else:
                meteorite.x += overlap_x
                meteorite.vel_x = bounced
            meteorite.vel_y += self.random.uniform(*_METEORITE_DRIFT)
        else:
            bounced = max(abs(meteorite.vel_y) * _BOUNCE_DAMPING, _BOUNCE_MIN_KICK)
            if rect.centery < hit.centery:
                meteorite.y -= overlap_y
                meteorite.vel_y = -bounced
            else:
                meteorite.y += overlap_y
                meteorite.vel_y = bounced
        meteorite.spin = self.random.uniform(*_METEORITE_SPIN)
        target.kick(impact_x * _IMPULSE_FACTOR, impact_y * _IMPULSE_FACTOR)
        self._burst(
            float(rect.centerx),
            float(rect.centery),
            _SPARK_COUNT,
            _SPARK_TTL,
            _SPARK_RADIUS,
            _SPARK_COLOR,
        )

    def _update_enemy(self, enemy: FxEnemy, dt: float) -> None:
        """Pendeln um den Anker, Höhe des Ziels anfliegen, bei Ausrichtung schießen."""
        enemy.x = enemy.anchor_x + _ENEMY_SWAY_X * math.sin(self._elapsed * 0.7 + enemy.phase)
        target = self._enemy_target(enemy)
        if target is None:
            goal = enemy.base_y + _ENEMY_IDLE_AMPLITUDE * math.sin(
                self._elapsed * 0.5 + enemy.phase
            )
        else:
            goal = target.y
        step = _ENEMY_HUNT_SPEED * dt
        if abs(goal - enemy.y) <= step:
            enemy.y = goal
        elif goal > enemy.y:
            enemy.y += step
        else:
            enemy.y -= step
        half_height = ENEMY_SIZE[1] / 2
        enemy.y = max(
            _ENEMY_MARGIN_Y + half_height,
            min(REFERENCE_SIZE[1] - _ENEMY_MARGIN_Y - half_height, enemy.y),
        )
        enemy.cooldown -= dt
        if (
            target is not None
            and enemy.cooldown <= 0
            and abs(target.y - enemy.y) <= _ENEMY_ALIGN_TOLERANCE
        ):
            aim_y = enemy.y + self.random.uniform(-_ENEMY_AIM_JITTER, _ENEMY_AIM_JITTER)
            self.projectiles.append(
                FxProjectile(x=enemy.rect.right, y=aim_y, vel_x=_FX_PROJECTILE_SPEED)
            )
            enemy.cooldown = self.random.uniform(*_ENEMY_COOLDOWN)

    def _enemy_target(self, enemy: FxEnemy) -> FxMeteorite | None:
        """Meteorit rechts des Gegners in dessen Bildhälfte (kleinste Höhendifferenz).

        Die Hälften-Aufteilung (oben/unten nach `base_y`) verhindert, dass beide
        Gegner demselben Ziel hinterherfliegen und aufeinander kleben.
        """
        half = REFERENCE_SIZE[1] / 2
        upper = enemy.base_y < half
        candidates = [
            m
            for m in self.meteorites
            if m.x > enemy.x + 50 and ((m.y < half) if upper else (m.y >= half))
        ]
        if not candidates:
            return None
        return min(candidates, key=lambda m: abs(m.y - enemy.y))

    def _update_projectiles(self, dt: float) -> None:
        """Bewegt Projektile; Treffer zerlegen Meteoriten in Trümmer."""
        remaining: list[FxProjectile] = []
        for projectile in self.projectiles:
            projectile.x += projectile.vel_x * dt
            hit = self._hit_meteorite(projectile)
            if hit is not None:
                self.meteorites.remove(hit)
                self._burst(
                    hit.x, hit.y, _DEBRIS_COUNT, _DEBRIS_TTL, _DEBRIS_RADIUS, METEORITE_COLOR
                )
                self._burst(hit.x, hit.y, _SPARK_COUNT, _SPARK_TTL, _SPARK_RADIUS, _SPARK_COLOR)
                continue
            if projectile.x > _PROJECTILE_END_X:
                self._burst(
                    projectile.x, projectile.y, (2, 3), _SPARK_TTL, _SPARK_RADIUS, _SPARK_COLOR
                )
                continue
            remaining.append(projectile)
        self.projectiles = remaining

    def _hit_meteorite(self, projectile: FxProjectile) -> FxMeteorite | None:
        """Erster Meteorit, den das Projektil gerade trifft; sonst None."""
        rect = projectile.rect
        for meteorite in self.meteorites:
            if rect.colliderect(meteorite.rect):
                return meteorite
        return None

    def _burst(
        self,
        x: float,
        y: float,
        count_range: tuple[int, int],
        ttl_range: tuple[float, float],
        radius: float,
        color: Color,
    ) -> None:
        """Streut Partikel in alle Richtungen um den Punkt (x, y)."""
        for _ in range(self.random.randint(*count_range)):
            direction = self.random.uniform(0.0, 2 * math.pi)
            speed = self.random.uniform(*_PARTICLE_SPEED)
            ttl = self.random.uniform(*ttl_range)
            self.particles.append(
                FxParticle(
                    x=x,
                    y=y,
                    vel_x=math.cos(direction) * speed,
                    vel_y=math.sin(direction) * speed,
                    ttl=ttl,
                    max_ttl=ttl,
                    radius=radius,
                    color=color,
                )
            )

    def _update_particles(self, dt: float) -> None:
        """Bewegt Partikel und entfernt abgelaufene."""
        remaining: list[FxParticle] = []
        for particle in self.particles:
            particle.ttl -= dt
            if particle.ttl <= 0:
                continue
            particle.x += particle.vel_x * dt
            particle.y += particle.vel_y * dt
            remaining.append(particle)
        self.particles = remaining

    # --- Zeichnen ----------------------------------------------------------

    def draw(self, ctx: RenderContext) -> None:
        """Zeichnet Projektile, Meteoriten, Gegner und Partikel (in dieser Reihenfolge)."""
        for projectile in self.projectiles:
            pygame.draw.rect(ctx.surface, PROJECTILE_COLOR, ctx.rect(projectile.rect))
        for meteorite in self.meteorites:
            self._draw_meteorite(ctx, meteorite)
        for enemy in self.enemies:
            self._draw_enemy(ctx, enemy)
        for particle in self.particles:
            self._draw_particle(ctx, particle)

    def _draw_meteorite(self, ctx: RenderContext, meteorite: FxMeteorite) -> None:
        """Sprite mit gerasterter Rotation (gecacht); Fallback: Kreis wie im Spiel."""
        target = ctx.rect(meteorite.rect)
        base = ctx.image(meteorite.image_name, target.size)
        if base is None:
            pygame.draw.circle(
                ctx.surface, METEORITE_COLOR, target.center, max(1, target.width // 2)
            )
            return
        bucket = round(meteorite.angle / _ANGLE_BUCKET_DEG) % (360 // _ANGLE_BUCKET_DEG)
        key = (meteorite.image_name, target.width, bucket)
        image = self._rotation_cache.get(key)
        if image is None:
            if len(self._rotation_cache) > _ROTATION_CACHE_MAX:
                self._rotation_cache.clear()
            image = pygame.transform.rotate(base, bucket * _ANGLE_BUCKET_DEG)
            self._rotation_cache[key] = image
        ctx.surface.blit(image, image.get_rect(center=target.center))

    def _draw_enemy(self, ctx: RenderContext, enemy: FxEnemy) -> None:
        """Nach rechts zeigendes Dreieck — Flugrichtung der Patrouille links."""
        rect = ctx.rect(enemy.rect)
        points = [(rect.right, rect.centery), (rect.left, rect.top), (rect.left, rect.bottom)]
        pygame.draw.polygon(ctx.surface, enemy.color, points)

    def _draw_particle(self, ctx: RenderContext, particle: FxParticle) -> None:
        """Kreis, der mit ablaufender Lebenszeit schrumpft."""
        vp = ctx.viewport
        fade = particle.ttl / particle.max_ttl
        radius = max(1, vp.s(particle.radius * fade))
        pygame.draw.circle(ctx.surface, particle.color, vp.point(particle.x, particle.y), radius)
