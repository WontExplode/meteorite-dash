"""Lightyears-Score und Zahlenformatierung für HUD und Death-Screen."""


def format_light_years(light_years: float) -> str:
    """Ganze Lichtjahre, sechsstellig mit führenden Nullen.

    >>> format_light_years(0.0)
    '000000'
    >>> format_light_years(1234.9)
    '001234'
    """
    return f"{int(light_years):06d}"


class DistanceScore:
    """Tracks travelled distance in light years.

    The rate multiplier is intentionally explicit so later difficulty phases,
    speed boosts or boss milestones can change score growth without changing the
    scoring formula itself.
    """

    def __init__(self, light_years_per_second: float) -> None:
        self.light_years = 0.0
        self.light_years_per_second = light_years_per_second
        self.rate_multiplier = 1.0

    def update(self, dt: float) -> None:
        """Zählt die Strecke dt-basiert hoch (Rate mal Multiplikator).

        >>> score = DistanceScore(10.0)
        >>> score.update(2.0)
        >>> score.light_years
        20.0

        Ein schnelleres Welttempo zahlt sich auch im Score aus:

        >>> score.set_rate_multiplier(3.0)
        >>> score.update(2.0)
        >>> score.formatted()
        '000080'
        """
        self.light_years += dt * self.light_years_per_second * self.rate_multiplier

    def set_rate_multiplier(self, multiplier: float) -> None:
        """Setzt den Multiplikator für spätere Speed-Phasen oder Boss-Abschnitte."""
        self.rate_multiplier = multiplier

    def formatted(self) -> str:
        """Aktueller Stand im HUD-Format (`format_light_years`)."""
        return format_light_years(self.light_years)


def format_coins(coins: int) -> str:
    """Münzzahl vierstellig mit führenden Nullen.

    >>> format_coins(7)
    '0007'
    """
    return f"{coins:04d}"
