"""The central owner of provider calls; consumers read the SQLite history."""

import random
import time
from datetime import datetime, timedelta, timezone

import httpx

from baselhack.ingestion import rhine, traffic, weather
from baselhack.interfaces import RealObservations

from .database import Database


def windows(start, end, chunk_hours):
    if start.utcoffset() is None or end.utcoffset() is None:
        raise ValueError("Ingestion windows require explicit UTC offsets")
    if start >= end or chunk_hours <= 0:
        raise ValueError("Ingestion window and chunk size must be positive")
    while start < end:
        stop = min(start + timedelta(hours=chunk_hours), end)
        yield start, stop
        start = stop


def download(kind, start, end, settings, client):
    if kind == "traffic":
        return traffic.download(
            start, end, settings["traffic_station_ids"], client=client
        )
    if kind == "rhine":
        return rhine.download(start, end, client=client)
    if kind == "weather":
        return weather.download(start, end, client=client)
    raise ValueError("Unknown observation kind")


def ingest_once(
    database: Database,
    settings: dict,
    *,
    start=None,
    end=None,
    client=None,
    fetch=download,
    sleep=time.sleep,
):
    """Persist providers independently; no DB write lock is held during HTTP.

    Successful windows overlap on refresh so delayed/revised records are retained.
    Failed or empty provider runs do not advance that stream's checkpoint.
    """
    if (
        settings["request_attempts"] < 1
        or settings["bootstrap_hours"] <= 0
        or settings["overlap_hours"] < 0
    ):
        raise ValueError("Invalid retry/bootstrap/overlap settings")
    end = end or datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    if end.utcoffset() is None or end > datetime.now(timezone.utc):
        raise ValueError(
            "Ingestion cutoff must be timezone-aware and not in the future"
        )
    end = end.astimezone(timezone.utc)
    if client is None:
        with httpx.Client(timeout=settings["request_timeout_seconds"]) as owned:
            return ingest_once(
                database,
                settings,
                start=start,
                end=end,
                client=owned,
                fetch=fetch,
                sleep=sleep,
            )
    database.initialize()
    reports = []
    for kind in ("traffic", "rhine", "weather"):
        stream = kind
        if kind == "traffic":
            stream += ":" + ",".join(sorted(set(settings["traffic_station_ids"])))
        checkpoint = database.checkpoint(stream)
        beginning = start or (
            checkpoint - timedelta(hours=settings["overlap_hours"])
            if checkpoint
            else end - timedelta(hours=settings["bootstrap_hours"])
        )
        if beginning.utcoffset() is None:
            raise ValueError("Ingestion start must be timezone-aware")
        beginning = beginning.astimezone(timezone.utc)
        chunks = list(windows(beginning, end, settings["chunk_hours"]))
        if kind == "weather":
            # MeteoSwiss serves whole CSV assets; avoid repeating each asset per day.
            chunks = [(beginning, end)]
        run_id = database.start_run(stream, beginning, end)
        received, added, empty = 0, 0, 0
        error = None
        try:
            for left, right in chunks:
                for attempt in range(settings["request_attempts"]):
                    try:
                        records, source = fetch(kind, left, right, settings, client)
                        break
                    except (ValueError, RuntimeError, httpx.HTTPError):
                        if attempt + 1 == settings["request_attempts"]:
                            raise
                        sleep(min(2**attempt, 8) + random.uniform(0, 0.25))
                received += len(records)
                empty += not records
                added += database.store_observations(kind, records, source, run_id)
        except (ValueError, RuntimeError, httpx.HTTPError) as exc:
            error = str(exc)
            status = "partial" if received else "failed"
        else:
            status = "no_data" if not received else "partial" if empty else "success"
            if empty:
                error = f"{empty} requested windows had no observations; coverage is incomplete"
        database.finish_run(run_id, status, received, added, error)
        reports.append(
            {
                "kind": kind,
                "stream": stream,
                "run_id": run_id,
                "status": status,
                "records_received": received,
                "records_added": added,
                "error": error,
            }
        )
    return reports


def import_observations(database: Database, observations: RealObservations):
    """Import the team's real cache through the same store, without network calls."""
    database.initialize()
    reports = []
    for kind in ("traffic", "rhine", "weather"):
        records = getattr(observations, kind)
        if not records:
            continue
        candidates = [
            source
            for source in observations.sources
            if (
                source.dataset == {"traffic": "100006", "rhine": "100089"}.get(kind)
                or kind == "weather"
                and "meteoswiss" in source.provider.lower()
                and "bas" in source.dataset.lower()
            )
        ]
        if len(candidates) != 1:
            raise ValueError(f"Cache requires exactly one declared source for {kind}")
        times = [item.interval_end if kind == "traffic" else item.t for item in records]
        run_id = database.start_run(f"cache:{kind}", min(times), max(times))
        added = database.store_observations(kind, records, candidates[0], run_id)
        database.finish_run(run_id, "success", len(records), added)
        reports.append(
            {"kind": kind, "records_received": len(records), "records_added": added}
        )
    return reports
