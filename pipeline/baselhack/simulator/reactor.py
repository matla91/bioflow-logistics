from datetime import datetime, timedelta, timezone


def readiness(scenario, rng):
    return datetime.fromisoformat(scenario["slot"]["charge_at"]).astimezone(
        timezone.utc
    ) + timedelta(
        minutes=float(rng.normal(0, scenario["site"]["reactor_drift_sd_min"]))
    )
