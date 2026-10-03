from datetime import datetime, timezone
from urllib.parse import urlencode

from .common import fetch


def temperatures(start, end):
    # UTC request avoids ambiguous DST hours; archive is reanalysis, not a station reading.
    query = urlencode(
        {
            "latitude": 51.92,
            "longitude": 4.48,
            "start_date": start,
            "end_date": end,
            "hourly": "temperature_2m",
            "timezone": "UTC",
        }
    )
    url = "https://archive-api.open-meteo.com/v1/archive?" + query
    payload = fetch(url, f"rotterdam_{start}_{end}.json").json()
    hourly = payload["hourly"]
    rows = [
        {
            "t": datetime.fromisoformat(t).replace(tzinfo=timezone.utc).isoformat(),
            "c": v,
        }
        for t, v in zip(hourly["time"], hourly["temperature_2m"])
        if v is not None
    ]
    return rows, url
