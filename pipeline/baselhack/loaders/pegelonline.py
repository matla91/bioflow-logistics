import httpx

from .common import cache, fetch

BASE = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"


def measurements(station, metric="W"):
    url = f"{BASE}/stations/{station}/{metric}/measurements.json?start=P31D"
    rows = fetch(url, f"{station}_{metric}.json").json()
    return [
        {"t": p["timestamp"], "v": p["value"]} for p in rows if p["value"] is not None
    ], url


def download():
    result = {}
    for station in ("KAUB", "Basel-Rheinhalle", "MAINZ", "KOBLENZ"):
        for metric in ("W", "Q"):
            try:
                rows, url = measurements(station, metric)
                result[f"{station}_{metric}"] = {"rows": rows, "source": url}
            except (httpx.HTTPError, ValueError) as error:
                result[f"{station}_{metric}"] = {
                    "rows": [],
                    "verification": f"TODO(verify): {station}/{metric}: {error}",
                }
    # Record actual coverage, not the unverified requested 1 September start.
    cache("river_window.json", result)
    return result
