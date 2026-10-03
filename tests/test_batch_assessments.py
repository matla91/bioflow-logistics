"""Batch readiness, causal timing and product evidence from stored SQLite inputs."""

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from baselhack.batch_assessment import MODEL_VERSION, analyze_batch
from baselhack.data_engine.database import Database, digest, utc
from baselhack.data_engine.ingest import import_observations
from baselhack.integration import create_app
from baselhack.interfaces import (
    BatchAnalysisProfile,
    InventoryLot,
    LogisticsAssumptions,
    ObservationSource,
    OperationalDataset,
    RealObservations,
    StoredBatchAssessment,
    WeatherObservation,
)
from baselhack.storage import ROOT, read_yaml
from fastapi.testclient import TestClient

AT = datetime(2026, 10, 3, 12, tzinfo=timezone.utc)
PROFILE_ID = "batch-default-v1"


@pytest.fixture(autouse=True)
def no_provider_calls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Batch analysis and read APIs must not fetch providers")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    from baselhack.ingestion import rhine, traffic, weather

    for module in (rhine, traffic, weather):
        monkeypatch.setattr(module, "download", forbidden)


@pytest.fixture
def database(tmp_path):
    result = Database(tmp_path / "batches.sqlite3")
    result.initialize()
    result.store_batch_profile(
        BatchAnalysisProfile(
            profile_id=PROFILE_ID,
            logistics=LogisticsAssumptions.model_validate(
                read_yaml("config/logistics.yaml")
            ),
        )
    )
    return result


@pytest.fixture
def demo(database):
    """Keep actual cache timestamps: September weather is stale for October runs."""
    import_observations(
        database,
        RealObservations.model_validate_json(
            (ROOT / "data/cache/logistics_basel.json").read_text()
        ),
    )
    dataset = OperationalDataset.model_validate_json(
        (ROOT / "output/operations-demo.json").read_text()
    )
    database.store_operations(dataset)
    return dataset


def fresh_weather(database, at=AT, *, temperature=5, retrieved_at=None):
    """Explicitly synthetic test weather; no real cache observations are shifted."""
    run = database.start_run("synthetic-test:weather", at, at)
    database.store_observations(
        "weather",
        [
            WeatherObservation(
                t=at,
                air_temperature_c=temperature,
                precipitation_mm=0,
                wind_speed_m_s=0,
            )
        ],
        ObservationSource(
            provider="Synthetic test weather",
            dataset="Synthetic BAS test fixture, not provider evidence",
            url="https://example.invalid/synthetic-test-weather",
            retrieved_at=retrieved_at or at,
            licence="Synthetic test fixture only",
        ),
        run,
    )


def deterministic_profile(database):
    assumptions = LogisticsAssumptions.model_validate(
        read_yaml("config/logistics.yaml")
    )
    assumptions = assumptions.model_copy(
        update={"n_runs": 100, "transport_sd_min": 0, "handling_sd_min": 0}
    )
    profile = BatchAnalysisProfile(
        profile_id="deterministic-test", logistics=assumptions
    )
    database.store_batch_profile(profile)
    return profile.profile_id


def operations(
    *,
    charge=AT + timedelta(hours=2),
    departure=AT - timedelta(hours=1),
    arrival=AT + timedelta(hours=1),
    actual_departure=AT - timedelta(hours=1),
    actual_arrival=None,
    temperatures=(),
    budget=120,
    scenario="normal",
    supply_quantity=50,
):
    """A small clearly synthetic domain case with no reserved stock by default."""
    return OperationalDataset.model_validate(
        {
            "dataset_id": "synthetic-domain-case",
            "seed": 10,
            "reference_at": AT,
            "materials": [
                {
                    "id": "material-case",
                    "name": "Synthetic test intermediate",
                    "range_c": [2, 8],
                    "budget_min": budget,
                }
            ],
            "shipments": [
                {
                    "id": "shipment-case",
                    "material_id": "material-case",
                    "lot_id": "lot-case",
                    "quantity_kg": 100,
                    "route_mode": "road",
                    "origin": "Rotterdam",
                    "destination": "Basel production site",
                    "planned_departure_at": departure,
                    "planned_arrival_at": arrival,
                    "actual_departure_at": actual_departure,
                    "actual_arrival_at": actual_arrival,
                    "status": "arrived"
                    if actual_arrival
                    else "in_transit"
                    if actual_departure
                    else "planned",
                    "scenario": scenario,
                }
            ],
            "batches": [
                {
                    "id": "batch-case",
                    "reactor": "test-reactor",
                    "material_id": "material-case",
                    "required_quantity_kg": 50,
                    "planned_charge_at": charge,
                    "status": "waiting_material" if charge < AT else "planned",
                }
            ],
            "supply_plans": [
                {
                    "batch_id": "batch-case",
                    "shipment_id": "shipment-case",
                    "quantity_kg": supply_quantity,
                }
            ],
            "inventory": [],
            "reservations": [],
            "readings": [
                {
                    "shipment_id": "shipment-case",
                    "at": at,
                    "product_c": value,
                    "ambient_c": 40,
                    "refrigerated": False,
                    "excursion_min": reported,
                }
                for at, value, reported in temperatures
            ],
            "assumptions": {"source": "Synthetic domain test fixture"},
        }
    )


def assess(database, dataset, *, as_of=AT, profile_id=PROFILE_ID, **kwargs):
    return analyze_batch(
        database,
        dataset.dataset_id,
        dataset.batches[0].id,
        as_of,
        profile_id=profile_id,
        **kwargs,
    )


def test_competing_stock_reservations_are_batch_specific(database, demo):
    first, second = [
        analyze_batch(database, demo.dataset_id, batch.id, AT)
        for batch in demo.batches[:2]
    ]
    assert first.production_readiness.released_reserved_quantity_kg == 50
    assert first.production_readiness.status == "RESERVED_STOCK_SUFFICIENT"
    assert first.recommendation.action is None
    assert second.production_readiness.released_reserved_quantity_kg == 30
    assert second.production_readiness.reservation_shortfall_kg == 20
    assert second.production_readiness.incoming_dependency_kg == 20
    assert second.production_readiness.uncovered_quantity_kg == 0
    assert second.production_readiness.status == "INCOMING_DEPENDENT"
    stock = next(
        item
        for item in second.production_readiness.stock_evidence
        if item.inventory_lot_id.endswith("stock-released")
    )
    assert stock.reserved_for_others_kg == 50
    assert stock.unreserved_quantity_kg == 0
    assert stock.eligible_reserved_quantity_kg == 30
    assert (
        sum(
            item.production_readiness.released_reserved_quantity_kg
            for item in (first, second)
        )
        == 80
    )


@pytest.mark.parametrize("offset_seconds", [-1, 0, 1])
def test_released_reservations_only_recommend_buffer_before_charge(
    database, offset_seconds
):
    dataset = operations(charge=AT + timedelta(seconds=offset_seconds))
    body = dataset.model_dump(mode="python")
    body["inventory"] = [
        {
            "id": "reserved-stock",
            "material_id": "material-case",
            "quantity_kg": 50,
            "available_at": AT - timedelta(days=1),
            "qa_status": "released",
        }
    ]
    body["reservations"] = [
        {
            "batch_id": "batch-case",
            "inventory_lot_id": "reserved-stock",
            "quantity_kg": 50,
        }
    ]
    dataset = OperationalDataset.model_validate(body)
    database.store_operations(dataset)
    record = assess(database, dataset)
    assert record.production_readiness.released_reserved_quantity_kg == 50
    assert record.production_readiness.reservation_shortfall_kg == 0
    assert record.recommendation.qa_release_authorized is False
    if offset_seconds > 0:
        assert record.recommendation.action == "BUFFER"
        assert record.recommendation.requires_approval_by == "operator"
    else:
        assert record.recommendation.action is None
        assert record.recommendation.alternatives == []
        assert "retrospective" in record.recommendation.reason.lower()
        assert "cannot be reconstructed" in record.recommendation.reason
        assert "cannot be reconstructed" in (
            record.production_readiness.stock_evidence[0].reason
        )


def test_retrospective_demo_preserves_stock_arrival_and_product_facts(database, demo):
    record = assess(database, demo)
    assert record.production_readiness.planned_charge_at < record.as_of
    assert record.recommendation.action is None
    assert record.recommendation.qa_review_required
    assert record.incoming_shipments[0].status == "ARRIVED"
    assert (
        record.incoming_shipments[0].actual_arrival_at
        == demo.shipments[0].actual_arrival_at
    )
    assert record.incoming_shipments[0].on_time_arrival_probability == 1
    assert record.product_temperature[0].observed_excursion_min == pytest.approx(
        99.496664
    )
    last_reading = max(
        (r for r in demo.readings if r.shipment_id == record.shipment_ids[0]),
        key=lambda r: r.at,
    )
    assert (
        record.product_temperature[0].reported_excursion_min
        == last_reading.excursion_min
    )


@pytest.mark.parametrize("charge", [AT - timedelta(seconds=1), AT])
def test_passed_charge_never_invokes_forward_logistics(database, monkeypatch, charge):
    dataset = operations(charge=charge)
    database.store_operations(dataset)
    fresh_weather(database)

    def forbidden(*args, **kwargs):
        raise AssertionError("No forward simulation at or after charge")

    monkeypatch.setattr("baselhack.batch_assessment.evaluate", forbidden)
    record = assess(database, dataset)
    assert record.recommendation.action is None
    assert record.recommendation.alternatives == []
    assert record.incoming_shipments[0].logistics is None
    assert record.incoming_shipments[0].on_time_arrival_probability is None


@pytest.mark.parametrize("qa_status", ["pending", "quarantined"])
def test_existing_reservation_cannot_bypass_current_qa_status(
    database, demo, qa_status
):
    with database.connect() as connection:
        connection.execute(
            "UPDATE inventory_lots SET qa_status=? WHERE id=?",
            (qa_status, demo.reservations[0].inventory_lot_id),
        )
    record = assess(database, demo)
    assert record.production_readiness.released_reserved_quantity_kg == 0
    assert record.production_readiness.reservation_shortfall_kg == 50
    assert record.recommendation.action != "BUFFER"
    assert record.recommendation.qa_release_authorized is False


@pytest.mark.parametrize(
    "available_at", [AT + timedelta(minutes=1), AT - timedelta(hours=1)]
)
def test_stock_must_exist_at_both_cutoff_and_charge(database, demo, available_at):
    # The first batch's charge is two hours before the dataset reference.
    with database.connect() as connection:
        connection.execute(
            "UPDATE inventory_lots SET available_at=? WHERE id=?",
            (utc(available_at), demo.reservations[0].inventory_lot_id),
        )
    assert (
        assess(database, demo).production_readiness.released_reserved_quantity_kg == 0
    )


def test_replay_before_operations_snapshot_cannot_invent_historical_qa(database, demo):
    record = assess(database, demo, as_of=demo.reference_at - timedelta(hours=1))
    assert record.production_readiness.released_reserved_quantity_kg == 0
    assert record.production_readiness.reservation_shortfall_kg == 50
    assert any(
        "history" in value.lower() or "snapshot" in value.lower()
        for value in record.limitations
    )


def test_unreserved_stock_never_covers_batch_demand(database):
    dataset = operations(supply_quantity=20)
    dataset.inventory = [
        InventoryLot.model_validate(
            {
                "id": "unreserved-stock",
                "material_id": "material-case",
                "quantity_kg": 1000,
                "available_at": AT - timedelta(days=1),
                "qa_status": "released",
            }
        )
    ]
    dataset = OperationalDataset.model_validate(dataset.model_dump())
    database.store_operations(dataset)
    record = assess(database, dataset)
    readiness = record.production_readiness
    assert readiness.released_reserved_quantity_kg == 0
    assert readiness.incoming_dependency_kg == 20
    assert readiness.uncovered_quantity_kg == 30
    assert readiness.status == "INSUFFICIENT_SUPPLY"
    assert (
        readiness.released_reserved_quantity_kg
        + readiness.incoming_dependency_kg
        + readiness.uncovered_quantity_kg
        == 50
    )
    assert record.recommendation.action != "BUFFER"


def test_delivered_released_lot_cannot_be_counted_again_as_incoming(database):
    dataset = operations(
        departure=AT - timedelta(hours=2),
        arrival=AT - timedelta(minutes=30),
        actual_departure=AT - timedelta(hours=2),
        actual_arrival=AT - timedelta(minutes=30),
    )
    body = dataset.model_dump(mode="python")
    body["batches"].append(
        {
            **body["batches"][0],
            "id": "competing-batch",
            "required_quantity_kg": 20,
        }
    )
    body["inventory"] = [
        {
            "id": "lot-case",
            "material_id": "material-case",
            "quantity_kg": 50,
            "available_at": AT - timedelta(minutes=30),
            "qa_status": "released",
            "shipment_id": "shipment-case",
        }
    ]
    body["reservations"] = [
        {"batch_id": batch, "inventory_lot_id": "lot-case", "quantity_kg": quantity}
        for batch, quantity in [("batch-case", 30), ("competing-batch", 20)]
    ]
    dataset = OperationalDataset.model_validate(body)
    database.store_operations(dataset)
    readiness = assess(database, dataset).production_readiness
    assert readiness.released_reserved_quantity_kg == 30
    assert readiness.reservation_shortfall_kg == 20
    assert readiness.incoming_dependency_kg == 0
    assert readiness.uncovered_quantity_kg == 20
    assert readiness.status == "INSUFFICIENT_SUPPLY"


def test_delay_case_label_does_not_invent_late_arrival(database, demo):
    batch = demo.batches[2]
    shipment = demo.shipments[2]
    assert shipment.scenario == "delay"
    assert shipment.planned_arrival_at < batch.planned_charge_at
    record = analyze_batch(database, demo.dataset_id, batch.id, AT)
    incoming = record.incoming_shipments[0]
    assert incoming.scheduled_after_charge is False
    assert incoming.actual_arrival_at is None
    assert incoming.status == "UNAVAILABLE"
    assert incoming.on_time_arrival_probability is None
    assert incoming.eta_p50 is None
    assert incoming.eta_p90 is None
    assert incoming.cold_chain_exposure_proxy_risk is None
    assert any(
        "weather" in value.lower() for value in [incoming.reason, *record.limitations]
    )
    temperature = record.product_temperature[0]
    assert temperature.observed_excursion_min == 0
    assert temperature.status == "OBSERVED_WITHIN_BUDGET"
    assert not temperature.complete_journey
    assert record.recommendation.qa_review_required
    assert record.recommendation.action != "QUARANTINE"
    assert any("whole-journey compliance" in note for note in temperature.limitations)


def test_actual_late_arrival_is_preserved_without_weather_model(database):
    dataset = operations(
        charge=AT - timedelta(minutes=90),
        departure=AT - timedelta(hours=3),
        arrival=AT - timedelta(hours=2),
        actual_departure=AT - timedelta(hours=3),
        actual_arrival=AT - timedelta(hours=1),
    )
    database.store_operations(dataset)
    incoming = assess(database, dataset).incoming_shipments[0]
    assert incoming.status == "ARRIVED"
    assert incoming.actual_arrival_at == AT - timedelta(hours=1)
    assert incoming.on_time_arrival_probability == 0
    assert incoming.eta_p50 == incoming.actual_arrival_at
    assert incoming.eta_p90 == incoming.actual_arrival_at
    assert incoming.cold_chain_exposure_proxy_risk is None


def test_modeled_remaining_time_uses_elapsed_actual_departure(database):
    dataset = operations(
        charge=AT + timedelta(hours=4),
        departure=AT - timedelta(hours=2),
        arrival=AT + timedelta(hours=1),
        actual_departure=AT - timedelta(minutes=30),
    )
    database.store_operations(dataset)
    fresh_weather(database)
    incoming = assess(
        database, dataset, profile_id=deterministic_profile(database)
    ).incoming_shipments[0]
    assert incoming.status == "MODELED"
    assert incoming.logistics.simulated_shipment.planned_remaining_min == 150
    assert incoming.eta_p50 == AT + timedelta(minutes=150)
    assert incoming.eta_p90 == incoming.eta_p50
    assert incoming.on_time_arrival_probability == 1
    assert incoming.cold_chain_exposure_proxy_risk == 0


def test_overdue_missing_arrival_has_no_invented_remaining_duration(database):
    dataset = operations(
        departure=AT - timedelta(hours=4),
        arrival=AT - timedelta(hours=1),
        actual_departure=AT - timedelta(hours=4),
    )
    database.store_operations(dataset)
    fresh_weather(database)
    incoming = assess(database, dataset).incoming_shipments[0]
    assert incoming.status == "UNAVAILABLE"
    assert incoming.on_time_arrival_probability is None
    assert incoming.eta_p50 is None
    assert incoming.logistics is None


def test_future_departure_exposes_late_schedule_and_missing_product_evidence(database):
    dataset = operations(
        departure=AT + timedelta(hours=1),
        arrival=AT + timedelta(hours=4),
        actual_departure=None,
    )
    database.store_operations(dataset)
    fresh_weather(database)
    record = assess(database, dataset)
    incoming = record.incoming_shipments[0]
    assert incoming.scheduled_after_charge is True
    assert incoming.status == "UNAVAILABLE"
    assert incoming.on_time_arrival_probability is None
    evidence = record.product_temperature[0]
    assert evidence.status == "UNAVAILABLE"
    assert evidence.reading_count == 0
    assert evidence.observed_excursion_min is None
    assert record.recommendation.qa_release_authorized is False


@pytest.mark.parametrize(
    "start,end,expected",
    [(5, 11, 30), (11, 5, 30), (8, 8, 0), (1, 1, 60), (1, 9, 15)],
)
def test_product_excursion_integrates_threshold_crossings(
    database, start, end, expected
):
    dataset = operations(
        temperatures=[(AT - timedelta(hours=1), start, 0), (AT, end, 999)]
    )
    database.store_operations(dataset)
    evidence = assess(database, dataset).product_temperature[0]
    assert evidence.reading_count == 2
    assert evidence.observed_excursion_min == pytest.approx(expected)
    assert evidence.reported_excursion_min == 999
    assert evidence.status == "OBSERVED_WITHIN_BUDGET"
    assert evidence.last_product_c == end
    assert evidence.last_product_outside_range is (end < 2 or end > 8)
    assert evidence.qa_release_authorized is False


def test_measured_budget_exceedance_is_separate_from_ambient_proxy(database):
    dataset = operations(
        temperatures=[(AT - timedelta(hours=1), 11, 0), (AT, 11, 1)],
        budget=30,
    )
    database.store_operations(dataset)
    fresh_weather(database, temperature=5)
    record = assess(database, dataset, profile_id=deterministic_profile(database))
    assert record.product_temperature[0].status == "OBSERVED_BUDGET_EXCEEDED"
    assert record.product_temperature[0].observed_excursion_min == 60
    assert record.product_temperature[0].reported_excursion_min == 1
    assert record.incoming_shipments[0].cold_chain_exposure_proxy_risk == 0
    assert record.recommendation.qa_review_required is True
    assert record.recommendation.qa_release_authorized is False


def test_sparse_product_history_reports_gap_without_inventing_excursion(database):
    dataset = operations(
        departure=AT - timedelta(hours=2),
        actual_departure=AT - timedelta(hours=2),
        temperatures=[(AT - timedelta(hours=2), 11, 0), (AT, 11, 120)],
    )
    database.store_operations(dataset)
    evidence = assess(database, dataset).product_temperature[0]
    assert evidence.reading_count == 2
    assert evidence.unobserved_interval_min >= 120
    assert evidence.complete_journey is False
    assert evidence.observed_excursion_min is None
    assert evidence.status == "UNAVAILABLE"
    assert evidence.limitations


def test_future_actuals_and_readings_are_excluded_from_cutoff(database):
    dataset = operations(temperatures=[(AT - timedelta(hours=1), 5, 0), (AT, 5, 0)])
    database.store_operations(dataset)
    original = assess(database, dataset)
    with database.connect() as connection:
        connection.execute(
            "UPDATE shipments SET actual_arrival_at=?,shipment_json=json_set(shipment_json,'$.actual_arrival_at',?) WHERE id=?",
            (
                utc(AT + timedelta(hours=1)),
                utc(AT + timedelta(hours=1)),
                "shipment-case",
            ),
        )
        connection.execute(
            "INSERT INTO shipment_readings VALUES (?,?,?,?,?,?,1)",
            ("shipment-case", utc(AT + timedelta(minutes=1)), 99, 99, 0, 10000),
        )
    snapshot = database.batch_snapshot(dataset.dataset_id, "batch-case", AT)
    assert snapshot.shipments[0].actual_arrival_at is None
    assert all(reading.at <= AT for reading in snapshot.shipments[0].readings)
    assert assess(database, dataset) == original


def test_generator_scenario_label_is_absent_from_inputs_and_predictions(database):
    dataset = operations()
    database.store_operations(dataset)
    fresh_weather(database)
    profile_id = deterministic_profile(database)
    original = assess(database, dataset, profile_id=profile_id)
    with database.connect() as connection:
        connection.execute(
            "UPDATE shipments SET shipment_json=json_set(shipment_json,'$.scenario','delay') WHERE id=?",
            ("shipment-case",),
        )
    assert assess(database, dataset, profile_id=profile_id) == original
    with database.connect() as connection:
        row = connection.execute(
            "SELECT evidence_json FROM batch_assessments WHERE assessment_id=?",
            (original.assessment_id,),
        ).fetchone()
    assert '"scenario"' not in row[0]


def test_batch_and_shipment_identifiers_are_links_not_predictors(database):
    original_dataset = operations()
    database.store_operations(original_dataset)
    fresh_weather(database)
    profile_id = deterministic_profile(database)
    original = assess(database, original_dataset, profile_id=profile_id)
    renamed = original_dataset.model_copy(deep=True)
    renamed.dataset_id = "renamed-domain-case"
    renamed.materials[0].id = "renamed-material"
    renamed.batches[0].id = "heat-delay-critical-batch"
    renamed.batches[0].material_id = "renamed-material"
    renamed.shipments[0].id = "delay-shipment-999"
    renamed.shipments[0].material_id = "renamed-material"
    renamed.shipments[0].lot_id = "renamed-lot"
    renamed.supply_plans[0].batch_id = renamed.batches[0].id
    renamed.supply_plans[0].shipment_id = renamed.shipments[0].id
    database.store_operations(renamed)
    result = assess(database, renamed, profile_id=profile_id)
    assert result.assessment_id != original.assessment_id
    assert result.recommendation == original.recommendation
    assert result.production_readiness == original.production_readiness
    expected = original.incoming_shipments[0]
    actual = result.incoming_shipments[0]
    assert actual.on_time_arrival_probability == expected.on_time_arrival_probability
    assert (
        actual.cold_chain_exposure_proxy_risk == expected.cold_chain_exposure_proxy_risk
    )
    assert actual.eta_p50 == expected.eta_p50
    assert actual.eta_p90 == expected.eta_p90


def test_known_at_excludes_later_weather_revision(database):
    dataset = operations()
    database.store_operations(dataset)
    fresh_weather(database, temperature=5)
    original = assess(database, dataset, known_at=AT)
    fresh_weather(database, temperature=40, retrieved_at=AT + timedelta(hours=1))
    assert assess(database, dataset, known_at=AT) == original
    revised = assess(database, dataset)
    assert revised.input_sha256 != original.input_sha256
    assert (
        revised.incoming_shipments[0].cold_chain_exposure_proxy_risk
        > original.incoming_shipments[0].cold_chain_exposure_proxy_risk
    )


def test_results_are_deterministic_immutable_and_hash_their_evidence(database, demo):
    original = assess(database, demo)
    assert assess(database, demo) == original
    assert (
        StoredBatchAssessment.model_validate_json(original.model_dump_json())
        == original
    )
    assert original.model_version == MODEL_VERSION
    assert original.dataset_id == demo.dataset_id
    assert original.batch_id == demo.batches[0].id
    assert original.shipment_ids == [demo.supply_plans[0].shipment_id]
    with database.connect() as connection:
        row = connection.execute(
            "SELECT evidence_json FROM batch_assessments WHERE assessment_id=?",
            (original.assessment_id,),
        ).fetchone()
        assert digest(json.loads(row[0])["inputs"]) == original.input_sha256
        assert (
            connection.execute("SELECT count(*) FROM batch_assessments").fetchone()[0]
            == 1
        )
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("UPDATE batch_assessments SET payload_json='{}'")
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute("DELETE FROM batch_assessments")


def test_model_version_change_appends_without_rewriting_previous_assessment(
    database, demo
):
    previous = assess(database, demo, model_version="previous-test-model")
    current = assess(database, demo)
    assert current.model_version == "batch-stored-evidence-v2"
    assert previous.input_sha256 != current.input_sha256
    assert previous.assessment_id != current.assessment_id
    assert database.batch_assessment(previous.assessment_id) == previous
    assert database.batch_assessment(current.assessment_id) == current
    assert database.batch_assessments(demo.dataset_id, current.batch_id)[0] == current
    assert assess(database, demo) == current


def test_equivalent_timezone_offsets_share_the_same_assessment(database, demo):
    original = assess(database, demo, known_at=AT)
    offset_cutoff = AT.astimezone(timezone(timedelta(hours=2)))
    assert (
        assess(database, demo, as_of=offset_cutoff, known_at=offset_cutoff) == original
    )


def test_knowledge_cutoff_before_dataset_capture_is_rejected(database, demo):
    with pytest.raises(ValueError):
        assess(database, demo, known_at=demo.reference_at - timedelta(seconds=1))
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM batch_assessments").fetchone()[0]
            == 0
        )


def test_worker_profile_is_immutable_and_required(database):
    profile = database.batch_profile(PROFILE_ID)
    assert database.store_batch_profile(profile) is False
    changed = profile.model_copy(update={"handling_min": 20})
    with pytest.raises(ValueError, match="different inputs"):
        database.store_batch_profile(changed)
    dataset = operations()
    database.store_operations(dataset)
    with pytest.raises(ValueError, match="profile"):
        assess(database, dataset, profile_id="missing-profile")


def test_read_api_filters_and_latest_never_compute_or_fetch(
    database, demo, monkeypatch
):
    first = assess(database, demo)
    later = assess(database, demo, as_of=AT + timedelta(minutes=1))
    other = analyze_batch(database, demo.dataset_id, demo.batches[1].id, AT)

    def forbidden(*args, **kwargs):
        raise AssertionError("Read API must serve persisted analysis only")

    monkeypatch.setattr("baselhack.batch_assessment.analyze_batch", forbidden)
    params = {
        "dataset_id": demo.dataset_id,
        "batch_id": demo.batches[0].id,
        "as_of": AT.isoformat(),
    }
    with TestClient(create_app(database)) as client:
        response = client.get("/api/integration/batch-assessments", params=params)
        assert response.status_code == 200
        assert response.json() == [first.model_dump(mode="json")]
        assert client.get(
            f"/api/integration/batch-assessments/{first.assessment_id}"
        ).json() == first.model_dump(mode="json")
        path = f"/api/integration/batches/{demo.batches[0].id}/assessments/latest"
        assert client.get(
            path, params={"dataset_id": demo.dataset_id, "as_of": AT.isoformat()}
        ).json() == first.model_dump(mode="json")
        assert client.get(
            path, params={"dataset_id": demo.dataset_id}
        ).json() == later.model_dump(mode="json")
        assert (
            client.get(
                path,
                params={
                    "dataset_id": demo.dataset_id,
                    "as_of": (AT - timedelta(seconds=1)).isoformat(),
                },
            ).status_code
            == 404
        )
        assert (
            client.get("/api/integration/batch-assessments/missing").status_code == 404
        )
        assert (
            client.get(
                "/api/integration/batch-assessments", params={"dataset_id": "missing"}
            ).json()
            == []
        )
        assert client.get(
            "/api/integration/batch-assessments", params={"batch_id": other.batch_id}
        ).json() == [other.model_dump(mode="json")]
        assert (
            client.get(
                "/api/integration/batch-assessments",
                params={"as_of": "not-a-timestamp"},
            ).status_code
            == 422
        )
        assert (
            client.post("/api/integration/batch-assessments", json={}).status_code
            == 405
        )
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM batch_assessments").fetchone()[0]
            == 3
        )


def test_unknown_batch_and_dataset_fail_without_persisting_results(database):
    with pytest.raises(ValueError):
        analyze_batch(database, "missing-dataset", "missing-batch", AT)
    with database.connect() as connection:
        assert (
            connection.execute("SELECT count(*) FROM batch_assessments").fetchone()[0]
            == 0
        )
