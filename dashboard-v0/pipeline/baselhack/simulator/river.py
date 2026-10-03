from datetime import datetime


def observed_at(series, at):
    values = [p for p in series if datetime.fromisoformat(p["t"]) <= at]
    if not values:
        raise ValueError("TODO(verify): no gauge observation at departure time")
    return max(values, key=lambda p: datetime.fromisoformat(p["t"]))["v"]


def barge_factor(scenario, at):
    thresholds = scenario["thresholds"]
    high = thresholds["basel_high_water_cm"]
    if (
        high is not None
        and scenario["rhine"]["basel_cm"]
        and observed_at(scenario["rhine"]["basel_cm"], at) >= high
    ):
        return None
    override = scenario.get("simulated_kaub_cm")
    level = (
        override
        if override is not None
        else observed_at(scenario["rhine"]["kaub_cm"], at)
    )
    for band in sorted(
        thresholds["river_bands"], key=lambda b: b["min_cm"], reverse=True
    ):
        if level >= band["min_cm"]:
            return band["factor"]
    return None
