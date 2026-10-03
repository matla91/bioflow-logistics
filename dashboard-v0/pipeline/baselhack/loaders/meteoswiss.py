import csv
from datetime import datetime, timezone

from .common import fetch

BASE = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/bas"


def temperatures():
    url = f"{BASE}/ogd-smn_bas_h_recent.csv"
    text = fetch(url, "bas_h_recent.csv").content.decode("latin-1")
    rows = []
    for row in csv.DictReader(text.splitlines(), delimiter=";"):
        if row.get("tre200h0"):
            # MeteoSwiss reference timestamps are UTC; convert explicitly later if desired.
            at = datetime.strptime(
                row["reference_timestamp"], "%d.%m.%Y %H:%M"
            ).replace(tzinfo=timezone.utc)
            rows.append({"t": at.isoformat(), "c": float(row["tre200h0"])})
    return rows, url
