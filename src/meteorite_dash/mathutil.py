"""Plattformstabile Mathematik für die Simulation (Issue #34).

`math.sin` und `math.hypot` rufen die C-Bibliothek des Systems; deren Ergebnisse
dürfen sich im letzten Bit zwischen Betriebssystemen unterscheiden. Für
bit-gleiche Replays auf fremden Rechnern (Daily Run) rechnet die Simulation den
Sinus als Polynom aus Grundrechenarten — IEEE-754-Addition/-Multiplikation sind
überall korrekt gerundet — und Distanzen über `math.sqrt`, das der Standard
ebenfalls exakt vorschreibt. Render-Code darf weiter `math.sin`/`math.cos` nutzen.
"""

import math

TWO_PI = 2.0 * math.pi
HALF_PI = math.pi / 2.0
# Taylor-Koeffizienten (-1)^k / (2k+1)! bis x^17. Auf [-pi/2, pi/2] liegt der
# Abbruchfehler unter 1e-13 — mehr Genauigkeit braucht kein Spielwert.
_SIN_COEFFS: tuple[float, ...] = tuple((-1.0) ** k / math.factorial(2 * k + 1) for k in range(9))


def det_sin(x: float) -> float:
    """Sinus aus Grundrechenarten: gleiches Bitmuster auf jeder Plattform."""
    x = x % TWO_PI  # [0, 2pi)
    if x > math.pi:
        x -= TWO_PI  # (-pi, pi]
    # Symmetrie sin(pi - x) = sin(x): auf [-pi/2, pi/2] zusammenfalten.
    if x > HALF_PI:
        x = math.pi - x
    elif x < -HALF_PI:
        x = -math.pi - x
    x2 = x * x
    # Horner-Schema in fester Reihenfolge -> identische Rundung überall.
    result = _SIN_COEFFS[-1]
    for coeff in reversed(_SIN_COEFFS[:-1]):
        result = result * x2 + coeff
    return result * x


def det_hypot(dx: float, dy: float) -> float:
    """Euklidischer Abstand über `sqrt` (IEEE-exakt) statt libm-`hypot`."""
    return math.sqrt(dx * dx + dy * dy)
