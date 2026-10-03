"""Basel 100006 hourly counts; sum approved distinct station lanes."""

from datetime import datetime
from typing import Iterable

import httpx

from ..interfaces import ObservationSource, TrafficObservation
from .common import (
    IngestionError,
    basel_records,
    number,
    provenance,
    timestamp,
    window,
)


def station_id(value: object) -> str:
    if isinstance(value, bool) or not str(value).isdigit():
        raise IngestionError("Traffic zst_id must be a numeric station identifier")
    return str(int(str(value)))


def parse_records(rows: list[dict]) -> list[TrafficObservation]:
    """Identical repeated lanes count once; any suspect lane fails closed.

    Each hour must include the station's lane set observed across this window.
    A changing lane configuration needs a separate window; no missing lane count
    is invented. A lane absent from the entire window cannot be detected here.
    """
    lanes: dict[tuple, float] = {}
    groups: dict[tuple, float] = {}
    station_lanes: dict[str, set[tuple]] = {}
    group_lanes: dict[tuple, set[tuple]] = {}
    for row in rows:
        station = station_id(row.get("zst_id"))
        start = timestamp(row.get("datetimefrom"), "datetimefrom")
        end = timestamp(row.get("datetimeto"), "datetimeto")
        if (end - start).total_seconds() != 3600:
            raise IngestionError("Traffic record must cover exactly one hour")
        if (
            isinstance(row.get("valuesapproved"), bool)
            or row.get("valuesapproved") != 1
        ):
            raise IngestionError(
                f"Unapproved or missing approval for traffic station {station}; "
                "partial station totals are unavailable"
            )
        if row.get("traffictype", "MIV") != "MIV":
            raise IngestionError("Traffic observation is not motorised vehicle data")
        count = number(row.get("total"), "traffic total")
        if count < 0 or not count.is_integer():
            raise IngestionError("Traffic total must be a nonnegative vehicle count")
        lane = number(row.get("lanecode"), "lanecode")
        direction = row.get("directionname")
        if lane < 0 or not lane.is_integer():
            raise IngestionError(
                "Traffic lane identifier must be a nonnegative integer"
            )
        lane = str(int(lane))
        if not isinstance(direction, str) or not direction.strip():
            raise IngestionError("Traffic lane and direction identifiers are required")
        direction = direction.strip()
        key = station, start, end, lane, direction
        if key in lanes:
            if lanes[key] != count:
                raise IngestionError(
                    f"Conflicting duplicate traffic lane at station {station}"
                )
            continue
        lanes[key] = count
        group = station, start, end
        groups[group] = groups.get(group, 0) + count
        lane_identity = lane, direction
        station_lanes.setdefault(station, set()).add(lane_identity)
        group_lanes.setdefault(group, set()).add(lane_identity)
    for (station, start, _), identities in group_lanes.items():
        if identities != station_lanes[station]:
            raise IngestionError(
                f"Incomplete or changing traffic lane coverage at station {station} "
                f"at {start.isoformat()}; select a window with stable lane coverage"
            )
    return [
        TrafficObservation(
            station_id=station,
            interval_start=start,
            interval_end=end,
            vehicle_count=count,
        )
        for (station, start, end), count in sorted(
            groups.items(), key=lambda item: (item[0][1], item[0][0])
        )
    ]


def download(
    start: datetime,
    end: datetime,
    stations: Iterable[str | int],
    *,
    client: httpx.Client | None = None,
) -> tuple[list[TrafficObservation], ObservationSource]:
    start, end = window(start, end)
    stations = sorted({station_id(station) for station in stations}, key=int)
    if not stations:
        raise IngestionError("Select at least one traffic counting station")
    station_filter = " or ".join(f"zst_id = {station}" for station in stations)
    where = (
        f"({station_filter}) and datetimefrom >= date'{start.isoformat()}' "
        f"and datetimeto <= date'{end.isoformat()}'"
    )
    rows, url = basel_records(
        "100006",
        where,
        "datetimefrom asc,zst_id asc,lanecode asc,directionname asc",
        client=client,
    )
    observations = parse_records(rows)
    if any(
        row.station_id not in stations
        or row.interval_start < start
        or row.interval_end > end
        for row in observations
    ):
        raise IngestionError(
            "Basel API returned traffic outside the selected window/stations"
        )
    return observations, provenance(
        "Amt für Mobilität, Open Data Basel-Stadt", "100006", url, "CC BY 4.0", rows
    )
