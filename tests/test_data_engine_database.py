"""History revisions, replay knowledge cutoffs and transactional persistence."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from baselhack.data_engine.database import Database
from baselhack.data_engine.operations import generate
from baselhack.interfaces import ObservationSource, WeatherObservation
from baselhack.storage import read_yaml

AT = datetime(2026, 9, 30, 12, tzinfo=timezone.utc)


@pytest.fixture
def database(tmp_path):
    result = Database(tmp_path / "history.sqlite3")
    result.initialize()
    return result


def source(at):
    return ObservationSource(
        provider="MeteoSwiss",
        dataset="BAS hourly",
        url="https://example.com/weather",
        retrieved_at=at,
        licence="CC BY 4.0",
    )


def test_observation_deduplication_revisions_and_known_at(database):
    original = WeatherObservation(t=AT, air_temperature_c=20)
    run = database.start_run("weather", AT - timedelta(hours=1), AT)
    assert database.store_observations("weather", [original], source(AT), run) == 1
    assert database.store_observations("weather", [original], source(AT), run) == 0
    corrected = original.model_copy(update={"air_temperature_c": 21})
    assert (
        database.store_observations(
            "weather", [corrected], source(AT + timedelta(hours=1)), run
        )
        == 1
    )
    assert database.observations(AT).weather[0].air_temperature_c == 21
    assert database.observations(AT, AT).weather[0].air_temperature_c == 20
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM external_observations").fetchone()[
                0
            ]
            == 2
        )
    with pytest.raises(ValueError, match="No stored"):
        database.observations(AT - timedelta(minutes=1))


def test_future_measurements_are_excluded_but_history_retained(database):
    run = database.start_run("weather", AT, AT + timedelta(hours=1))
    database.store_observations(
        "weather",
        [
            WeatherObservation(t=AT, air_temperature_c=20),
            WeatherObservation(t=AT + timedelta(hours=1), air_temperature_c=30),
        ],
        source(AT),
        run,
    )
    assert len(database.observations(AT).weather) == 1
    assert len(database.observations(AT + timedelta(hours=1)).weather) == 2


def test_only_success_advances_checkpoint(database):
    for status in ("failed", "partial", "no_data", "running"):
        run = database.start_run("traffic:402", AT - timedelta(hours=1), AT)
        database.finish_run(run, status, 0, 0)
        assert database.checkpoint("traffic:402") is None
    database.finish_run(run, "success", 1, 1)
    assert database.checkpoint("traffic:402") == AT
    assert database.checkpoint("traffic:403") is None


def test_operations_persist_once_and_refuse_overwrite(database):
    dataset = generate(read_yaml("config/operations_demo.yaml"))
    assert database.store_operations(dataset)
    assert not database.store_operations(dataset)
    with database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM batches").fetchone()[0] == 18
        assert connection.execute("SELECT count(*) FROM shipments").fetchone()[0] == 12
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        stock = connection.execute(
            "SELECT unreserved_quantity_kg FROM available_inventory WHERE qa_status='released'"
        ).fetchone()[0]
        assert stock == 0
    changed = dataset.model_copy(update={"seed": dataset.seed + 1})
    with pytest.raises(ValueError, match="different inputs"):
        database.store_operations(changed)


def test_unknown_material_rejects_entire_dataset(database):
    dataset = generate(read_yaml("config/operations_demo.yaml"))
    dataset.batches[0].material_id = "missing"
    with pytest.raises(ValueError, match="Unknown material"):
        database.store_operations(dataset)
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM operational_datasets").fetchone()[
                0
            ]
            == 0
        )


def test_collector_lock_prevents_overlapping_provider_calls(database):
    with (
        database.collector_lock(),
        pytest.raises(RuntimeError, match="Another collector"),
        database.collector_lock(),
    ):
        pytest.fail("Duplicate collector acquired the lock")
    with database.collector_lock():
        pass


def test_sql_rejects_stock_overallocation_and_pending_qa_stock(database):
    dataset = generate(read_yaml("config/operations_demo.yaml"))
    database.store_operations(dataset)
    with database.connect() as connection:
        with pytest.raises(sqlite3.IntegrityError, match="Stock reservation"):
            connection.execute(
                "UPDATE stock_reservations SET quantity_kg=50 WHERE batch_id=?",
                (dataset.batches[1].id,),
            )
        pending = next(
            lot.id for lot in dataset.inventory if lot.qa_status == "pending"
        )
        with pytest.raises(sqlite3.IntegrityError, match="Stock reservation"):
            connection.execute(
                "INSERT INTO stock_reservations VALUES (?,?,10)",
                (dataset.batches[2].id, pending),
            )
