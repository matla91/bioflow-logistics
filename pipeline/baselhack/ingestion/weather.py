"""MeteoSwiss BAS (Basel/Binningen) hourly ambient observations."""

import csv
from datetime import datetime, timezone
from io import StringIO

import httpx

from ..interfaces import ObservationSource, WeatherObservation
from .common import IngestionError, get, number, provenance, timestamp, window

BASE = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas"


def parse_csv(text: str) -> list[WeatherObservation]:
    reader = csv.DictReader(StringIO(text.lstrip("\ufeff")), delimiter=";")
    required = {"station_abbr", "reference_timestamp", "tre200h0"}
    if not required.issubset(reader.fieldnames or []):
        raise IngestionError("MeteoSwiss hourly CSV is missing required columns")
    observations: dict[datetime, WeatherObservation] = {}
    for row in reader:
        if row.get("station_abbr") != "BAS":
            raise IngestionError(
                "Weather observations must be from BAS Basel/Binningen"
            )
        temperature = number(row.get("tre200h0"), "tre200h0", optional=True)
        if temperature is None:
            continue
        try:
            at = datetime.strptime(row["reference_timestamp"], "%d.%m.%Y %H:%M")
        except (ValueError, TypeError) as exc:
            raise IngestionError("Invalid MeteoSwiss reference_timestamp") from exc
        if at.minute != 0:
            raise IngestionError("MeteoSwiss hourly observations must end on the hour")
        # The source timestamp ends the preceding hourly measurement interval.
        at = at.replace(tzinfo=timezone.utc)
        observation = WeatherObservation(
            t=at,
            air_temperature_c=temperature,
            precipitation_mm=number(row.get("rre150h0"), "rre150h0", optional=True),
            wind_speed_m_s=number(row.get("fkl010h0"), "fkl010h0", optional=True),
            relative_humidity_pct=number(
                row.get("ure200h0"), "ure200h0", optional=True
            ),
        )
        if at in observations and observations[at] != observation:
            raise IngestionError(
                f"Conflicting weather observations at {at.isoformat()}"
            )
        observations[at] = observation
    return [observations[at] for at in sorted(observations)]


def download(
    start: datetime,
    end: datetime,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
) -> tuple[list[WeatherObservation], ObservationSource]:
    """Combine historical decade, recent and now files for a bounded UTC window."""
    start, end = window(start, end)
    now = timestamp(now or datetime.now(timezone.utc), "now")
    if end > now:
        raise IngestionError("Weather download requests future observations")
    if client is None:
        with httpx.Client(timeout=30) as owned_client:
            return download(start, end, client=owned_client, now=now)
    urls: list[str] = []
    if start.year < now.year:
        for decade in range(start.year // 10 * 10, min(end.year, now.year - 1) + 1, 10):
            urls.append(f"{BASE}/ogd-smn_bas_h_historical_{decade}-{decade + 9}.csv")
    if end.year == now.year:
        urls.append(f"{BASE}/ogd-smn_bas_h_recent.csv")
        # Provider now contains yesterday 12UTC onward; recent ends yesterday.
        if end.date() == now.date():
            urls.append(f"{BASE}/ogd-smn_bas_h_now.csv")
    observations: dict[datetime, WeatherObservation] = {}
    content: list[bytes] = []
    for url in urls:
        response = get(client, url)
        content.append(response.content)
        rows = parse_csv(response.content.decode("cp1252"))
        for row in rows:
            if start <= row.t <= end:
                # Overlap between recent and now is intentional. Prefer now's
                # newest revision, preserving provider values rather than means.
                observations[row.t] = row
    return [observations[at] for at in sorted(observations)], provenance(
        "MeteoSwiss",
        "SwissMetNet BAS hourly observations",
        " | ".join(urls),
        "CC BY 4.0; Source: MeteoSwiss",
        b"\n".join(content),
    )
