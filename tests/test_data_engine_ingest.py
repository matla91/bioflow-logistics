"""Independent provider failures, incremental overlaps and shared ML inputs."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from baselhack.data_engine.database import Database
from baselhack.data_engine.ingest import import_observations, ingest_once
from baselhack.interfaces import (
    RealObservations,
    RhineObservation,
    TrafficObservation,
    WeatherObservation,
)
from baselhack.storage import read_json, read_yaml

AT = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


@pytest.fixture
def database(tmp_path):
    result = Database(tmp_path / "central.sqlite3")
    result.initialize()
    return result


def fixture_fetch(kind, start, end, settings, client):
    source = {
        "provider": "MeteoSwiss" if kind == "weather" else "Basel",
        "dataset": {"weather": "BAS hourly", "traffic": "100006", "rhine": "100089"}[
            kind
        ],
        "url": "https://example.com/observations",
        "licence": "fixture",
        "retrieved_at": AT,
    }
    record = {
        "weather": WeatherObservation(t=end, air_temperature_c=20),
        "rhine": RhineObservation(t=end, level_masl=245, discharge_m3_s=500),
        "traffic": TrafficObservation(
            station_id="402",
            interval_start=end - timedelta(hours=1),
            interval_end=end,
            vehicle_count=100,
        ),
    }[kind]
    return [record], source


def test_repeat_collection_has_no_duplicate_observations(database):
    settings = read_yaml("config/data_engine.yaml")
    with httpx.Client() as client:
        first = ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=1),
            end=AT,
            client=client,
            fetch=fixture_fetch,
        )
        second = ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=1),
            end=AT,
            client=client,
            fetch=fixture_fetch,
        )
    assert [r["records_added"] for r in first] == [1, 1, 1]
    assert [r["records_added"] for r in second] == [0, 0, 0]
    assert len(database.observations(AT).sources) == 3


def test_provider_failure_does_not_stop_other_streams_or_advance_cursor(database):
    settings = read_yaml("config/data_engine.yaml")
    attempts = []

    def fetch(kind, *args):
        if kind == "traffic":
            attempts.append(kind)
            raise ValueError("provider unavailable")
        return fixture_fetch(kind, *args)

    with httpx.Client() as client:
        reports = ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=1),
            end=AT,
            client=client,
            fetch=fetch,
            sleep=lambda _: None,
        )
    assert [r["status"] for r in reports] == ["failed", "success", "success"]
    assert len(attempts) == 3
    assert database.checkpoint("traffic:402") is None
    assert database.checkpoint("weather") == AT


def test_partially_failed_windows_keep_previous_data(database):
    settings = {
        **read_yaml("config/data_engine.yaml"),
        "chunk_hours": 1,
        "request_attempts": 1,
    }

    def fetch(kind, start, *args):
        if start == AT - timedelta(hours=1):
            raise ValueError("second chunk failed")
        return fixture_fetch(kind, start, *args)

    with httpx.Client() as client:
        reports = ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=2),
            end=AT,
            client=client,
            fetch=fetch,
        )
    assert all(
        r["status"] == "partial" and r["records_added"] == 1 for r in reports[:2]
    )
    assert reports[2]["status"] == "success"
    assert database.checkpoint("traffic:402") is None
    assert database.observations(AT).weather


def test_empty_streams_record_no_data_without_advancing_checkpoint(database):
    settings = read_yaml("config/data_engine.yaml")

    def fetch(kind, *args):
        _, source = fixture_fetch(kind, *args)
        return [], source

    with httpx.Client() as client:
        reports = ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=1),
            end=AT,
            client=client,
            fetch=fetch,
        )
    assert all(report["status"] == "no_data" for report in reports)
    assert all(database.checkpoint(report["stream"]) is None for report in reports)
    with pytest.raises(ValueError, match="No stored observations"):
        database.observations(AT)


def test_incremental_run_uses_own_stream_overlap(database):
    settings = read_yaml("config/data_engine.yaml")
    with httpx.Client() as client:
        ingest_once(
            database,
            settings,
            start=AT - timedelta(hours=1),
            end=AT,
            client=client,
            fetch=fixture_fetch,
        )
        calls = []

        def fetch(kind, start, *args):
            calls.append(start)
            return fixture_fetch(kind, start, *args)

        ingest_once(
            database, settings, end=AT + timedelta(hours=1), client=client, fetch=fetch
        )
    assert calls == [AT - timedelta(hours=2)] * 3


def test_offline_cache_roundtrip_uses_existing_ml_contract(database):
    original = RealObservations.model_validate(
        read_json("data/cache/logistics_basel.json")
    )
    reports = import_observations(database, original)
    assert all(r["records_added"] > 0 for r in reports)
    cutoff = max(item.t for item in original.weather)
    restored = database.observations(cutoff)
    assert restored.weather
    assert restored.rhine
    assert restored.traffic
    assert all(r["records_added"] == 0 for r in import_observations(database, original))
