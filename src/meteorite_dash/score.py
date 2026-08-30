def format_light_years(light_years: float) -> str:
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
        self.light_years += dt * self.light_years_per_second * self.rate_multiplier

    def set_rate_multiplier(self, multiplier: float) -> None:
        self.rate_multiplier = multiplier

    def formatted(self) -> str:
        return format_light_years(self.light_years)


def format_coins(coins: int) -> str:
    return f"{coins:04d}"
