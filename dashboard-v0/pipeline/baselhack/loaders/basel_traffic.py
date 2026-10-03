from urllib.parse import urlencode

from .common import cache, fetch

BASE = "https://data.bs.ch/api/explore/v2.1/catalog/datasets"


def records(dataset, where=None):
    query = {"limit": 100}
    if where:
        query["where"] = where
    url = f"{BASE}/{dataset}/records?" + urlencode(query)
    return fetch(url, f"traffic_{dataset}.json").json()["results"], url


def download():
    result = {}
    for dataset in ("100006", "100356", "100038"):
        rows, url = records(dataset)
        result[dataset] = {"rows": rows, "source": url}
    cache(
        "traffic_sample.json",
        {key: value for key, value in result.items() if key != "100038"},
    )
    return result


def factors(rows, station_ids, thresholds):
    if not station_ids:
        raise ValueError("TODO(verify): traffic counting-station selection")
    totals = {}
    for row in rows:
        if str(row["zst_id"]) in station_ids:
            hour = f"{int(row['hourfrom']):02d}"
            totals.setdefault(hour, []).append(float(row["total"]))
    return {
        h: min(
            thresholds["traffic_max_factor"],
            1
            + sum(v)
            / len(v)
            / thresholds["traffic_capacity_per_hour"]
            * thresholds["traffic_sensitivity"],
        )
        for h, v in totals.items()
    }
