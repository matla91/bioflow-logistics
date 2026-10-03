"""Priority 3 skeleton. Negative gauge readings alone are not anomalies."""


def check(station, at, level, discharge=None, neighbours=None):
    if discharge is None or not neighbours:
        return {
            "station": station,
            "t": at,
            "flag": "unverified",
            "detail": "TODO(verify): align discharge and neighbouring gauge evidence; negative gauge datum is allowed",
        }
    return {
        "station": station,
        "t": at,
        "flag": "not_evaluated",
        "detail": "TODO(verify): calibrate cross-gauge consistency; no plausibility claim yet",
    }
