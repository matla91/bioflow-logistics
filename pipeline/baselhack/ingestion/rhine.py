"""Basel 100089 water level and discharge observations (FOEN station 2289)."""

from datetime import datetime

import httpx

from ..interfaces import ObservationSource, RhineObservation
from .common import (
    IngestionError,
    basel_records,
    number,
    provenance,
    timestamp,
    window,
)


def parse_records(rows: list[dict]) -> list[RhineObservation]:
    observations: dict[datetime, RhineObservation] = {}
    for row in rows:
        at = timestamp(row.get("timestamp"), "timestamp")
        level = number(row.get("pegel"), "pegel", optional=True)
        gauge_cm = number(row.get("pegelhoehe"), "pegelhoehe", optional=True)
        discharge = number(row.get("abfluss"), "abfluss", optional=True)
        # Provider metadata defines pegelhoehe relative to precisely 240 m ASL.
        if gauge_cm is not None:
            converted = 240 + gauge_cm / 100
            if level is None:
                level = converted
            elif abs(level - converted) > 0.001:
                raise IngestionError(
                    "Rhine pegel and pegelhoehe have conflicting units"
                )
        if level is None and discharge is None:
            raise IngestionError("Rhine record has neither level nor discharge")
        if discharge is not None and discharge < 0:
            raise IngestionError("Rhine abfluss cannot be negative")
        observation = RhineObservation(t=at, level_masl=level, discharge_m3_s=discharge)
        if at in observations and observations[at] != observation:
            raise IngestionError(f"Conflicting Rhine observations at {at.isoformat()}")
        observations[at] = observation
    return [observations[at] for at in sorted(observations)]


def download(
    start: datetime, end: datetime, *, client: httpx.Client | None = None
) -> tuple[list[RhineObservation], ObservationSource]:
    start, end = window(start, end)
    where = (
        f"timestamp >= date'{start.isoformat()}' "
        f"and timestamp <= date'{end.isoformat()}'"
    )
    rows, url = basel_records("100089", where, "timestamp asc", client=client)
    observations = parse_records(rows)
    if any(not start <= row.t <= end for row in observations):
        raise IngestionError(
            "Basel API returned a Rhine observation outside the window"
        )
    return observations, provenance(
        "Bundesamt für Umwelt BAFU via Open Data Basel-Stadt",
        "100089",
        url,
        "CC0 1.0",
        rows,
    )
