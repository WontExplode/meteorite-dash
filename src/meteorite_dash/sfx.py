"""Prozedural erzeugte Soundeffekte — Retro-Blips ohne Audio-Assets.

Für Treffer, Explosionen, Pickups und Schaden liegen keine Audiodateien im
Repo. Statt welche zu erfinden, synthetisiert dieses Modul sie: jeder Effekt
ist ein Rezept aus Stimmen (`Voice`), jede Stimme eine Folge von Abschnitten
(`Segment`) mit Frequenzverlauf, Wellenform und Hüllkurve. Die Stimmen werden
gemischt, ins Format des laufenden Mixers gepackt und als `pygame.mixer.Sound`
gecacht.

Reine Ausgabe: kein Sim-Pfad, kein Einfluss auf Replays. Ohne initialisierten
Mixer (oder bei einem exotischen Sample-Format) bleibt alles ein stilles No-op.
"""

import math
import random
from array import array
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import pygame

Wave = Literal["square", "sine", "noise"]

# Rauschen mit festem Seed: derselbe Effekt klingt in jedem Lauf gleich.
_NOISE_SEED = 20260831
# Kurze Ein-/Ausblende gegen Knackser an den Puffergrenzen.
_FADE_SECONDS = 0.004


@dataclass(frozen=True)
class Segment:
    """Ein Abschnitt einer Stimme: Frequenzrampe mit Hüllkurve.

    `decay` ist der Exponent der abfallenden Hüllkurve (1 = linear, größer =
    schneller weg); `start_hz`/`end_hz` bilden eine lineare Rampe.
    """

    seconds: float
    start_hz: float = 440.0
    end_hz: float | None = None  # None = konstante Tonhöhe
    wave: Wave = "square"
    volume: float = 1.0
    decay: float = 1.5


# Eine Stimme ist eine Folge von Abschnitten; ein Rezept mischt mehrere Stimmen.
Voice = tuple[Segment, ...]
Recipe = tuple[Voice, ...]


class Sfx(Enum):
    """Katalog der Effekte; Werte sind zugleich die Cache-Schlüssel."""

    HIT = "hit"
    EXPLOSION = "explosion"
    COIN = "coin"
    BONUS = "bonus"
    AMMO = "ammo"
    SHIELD = "shield"
    DAMAGE = "damage"
    DEATH = "death"


RECIPES: dict[Sfx, Recipe] = {
    # Trockener Aufschlag: kurzer Abwärts-Blip mit etwas Rauschen darüber.
    Sfx.HIT: (
        (Segment(0.07, 900.0, 320.0, "square", 0.6, 2.5),),
        (Segment(0.05, 0.0, 0.0, "noise", 0.35, 4.0),),
    ),
    # Explosion: Rauschwolke mit tiefem Bauch darunter.
    Sfx.EXPLOSION: (
        (Segment(0.42, 0.0, 0.0, "noise", 0.8, 2.2),),
        (Segment(0.35, 160.0, 45.0, "square", 0.5, 2.0),),
    ),
    # Klassischer Münz-Zweiklang.
    Sfx.COIN: (
        (
            Segment(0.05, 988.0, 988.0, "square", 0.45, 0.6),
            Segment(0.12, 1319.0, 1319.0, "square", 0.45, 2.0),
        ),
    ),
    # Vollständiges Muster: kleines Arpeggio nach oben.
    Sfx.BONUS: (
        (
            Segment(0.06, 784.0, 784.0, "square", 0.4, 0.5),
            Segment(0.06, 988.0, 988.0, "square", 0.4, 0.5),
            Segment(0.06, 1319.0, 1319.0, "square", 0.4, 0.5),
            Segment(0.16, 1568.0, 1568.0, "square", 0.45, 2.0),
        ),
    ),
    # Nachladen: kurzer Aufwärts-Sweep.
    Sfx.AMMO: ((Segment(0.14, 320.0, 940.0, "square", 0.4, 1.0),),),
    # Schild hält: heller Sinus-Sweep plus kurzes Zischen.
    Sfx.SHIELD: (
        (Segment(0.22, 420.0, 1250.0, "sine", 0.55, 1.4),),
        (Segment(0.10, 0.0, 0.0, "noise", 0.25, 3.0),),
    ),
    # Treffer am Schiff: dumpfer Schlag.
    Sfx.DAMAGE: (
        (Segment(0.28, 220.0, 70.0, "square", 0.7, 1.8),),
        (Segment(0.16, 0.0, 0.0, "noise", 0.45, 2.5),),
    ),
    # Tod: langer Absturz mit Trümmerrauschen.
    Sfx.DEATH: (
        (Segment(0.75, 420.0, 55.0, "square", 0.7, 1.4),),
        (Segment(0.60, 0.0, 0.0, "noise", 0.55, 1.8),),
    ),
}


class SoundBank:
    """Baut die Effekte beim ersten Abspielen und hält sie danach im Cache.

    Ohne laufenden Mixer (Tests ohne Audio, `pygame.mixer` nicht initialisiert)
    ist jede Methode ein No-op — die Szene muss nichts prüfen.
    """

    def __init__(self) -> None:
        self._sounds: dict[Sfx, pygame.mixer.Sound | None] = {}

    def play(self, effect: Sfx, volume: float = 1.0) -> None:
        """Spielt einen Effekt; unbekanntes Mixer-Format oder Fehler bleiben still."""
        sound = self._sound(effect)
        if sound is None:
            return
        sound.set_volume(max(0.0, min(1.0, volume)))
        sound.play()

    def _sound(self, effect: Sfx) -> pygame.mixer.Sound | None:
        if effect not in self._sounds:
            self._sounds[effect] = _build(RECIPES[effect])
        return self._sounds[effect]


def _build(recipe: Recipe) -> pygame.mixer.Sound | None:
    """Rendert ein Rezept in einen Mixer-Puffer; None, wenn das nicht geht."""
    mixer_format = pygame.mixer.get_init()
    if mixer_format is None:
        return None
    rate, size, channels = mixer_format
    buffer = _to_buffer(_mix(recipe, rate), size, channels)
    if buffer is None:
        return None
    try:
        return pygame.mixer.Sound(buffer=buffer)
    except pygame.error:
        return None


def _mix(recipe: Recipe, rate: int) -> list[float]:
    """Summiert alle Stimmen; die längste bestimmt die Gesamtlänge."""
    voices = [_render_voice(voice, rate) for voice in recipe]
    length = max((len(voice) for voice in voices), default=0)
    mixed = [0.0] * length
    for voice in voices:
        for index, value in enumerate(voice):
            mixed[index] += value
    return mixed


def _render_voice(voice: Voice, rate: int) -> list[float]:
    """Hängt die Abschnitte einer Stimme aneinander (Phase läuft durch)."""
    rng = random.Random(_NOISE_SEED)
    samples: list[float] = []
    phase = 0.0
    for segment in voice:
        segment_samples, phase = _render_segment(segment, rate, phase, rng)
        samples.extend(segment_samples)
    return _fade_edges(samples, rate)


def _render_segment(
    segment: Segment, rate: int, phase: float, rng: random.Random
) -> tuple[list[float], float]:
    """Ein Abschnitt als Samples; gibt die Endphase für den nächsten zurück."""
    count = max(1, round(segment.seconds * rate))
    end_hz = segment.end_hz if segment.end_hz is not None else segment.start_hz
    samples: list[float] = []
    for index in range(count):
        progress = index / count
        phase += (segment.start_hz + (end_hz - segment.start_hz) * progress) / rate
        if segment.wave == "noise":
            value = rng.uniform(-1.0, 1.0)
        elif segment.wave == "sine":
            value = math.sin(2 * math.pi * phase)
        else:
            value = 1.0 if phase % 1.0 < 0.5 else -1.0
        samples.append(value * segment.volume * (1.0 - progress) ** segment.decay)
    return samples, phase


def _fade_edges(samples: list[float], rate: int) -> list[float]:
    """Blendet Anfang und Ende weich — sonst knackt der Lautsprecher."""
    fade = min(round(_FADE_SECONDS * rate), len(samples) // 2)
    for index in range(fade):
        factor = index / fade
        samples[index] *= factor
        samples[-1 - index] *= factor
    return samples


def _to_buffer(samples: list[float], size: int, channels: int) -> bytes | None:
    """Packt Samples ins Mixer-Format; None bei nicht unterstützter Bittiefe."""
    if size not in (-16, 16):
        return None
    signed = size < 0
    peak = 32767
    data = array("h" if signed else "H")
    for value in samples:
        sample = round(max(-1.0, min(1.0, value)) * peak)
        data.append(sample if signed else sample + 32768)
    if channels > 1:
        # Mono auf alle Kanäle spiegeln: der Mixer erwartet verschränkte Frames.
        spread = array(data.typecode)
        for sample in data:
            spread.extend([sample] * channels)
        data = spread
    return data.tobytes()
