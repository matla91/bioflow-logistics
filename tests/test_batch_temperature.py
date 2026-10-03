"""Sample-based temperature evidence remains separate from QA and source totals."""

from datetime import datetime, timedelta, timezone

import pytest
from baselhack.batch_temperature import product_temperature
from baselhack.interfaces import BatchShipmentSnapshot, OperationalMaterial

START = datetime(2026, 10, 3, tzinfo=timezone.utc)


def material(budget=120):
    return OperationalMaterial(
        id="material", name="Synthetic product", range_c=(2, 8), budget_min=budget
    )


def shipment(samples, arrival=None):
    return BatchShipmentSnapshot(
        id="shipment",
        material_id="material",
        lot_id="lot",
        quantity_kg=50,
        route_mode="road",
        origin="Synthetic origin",
        destination="Synthetic destination",
        planned_departure_at=START,
        planned_arrival_at=START + timedelta(hours=4),
        actual_departure_at=START,
        actual_arrival_at=START + timedelta(minutes=arrival)
        if arrival is not None
        else None,
        readings=[
            {
                "shipment_id": "shipment",
                "at": START + timedelta(minutes=minute),
                "product_c": product_c,
                "ambient_c": 20,
                "refrigerated": False,
                "excursion_min": reported,
            }
            for minute, product_c, reported in samples
        ],
    )


@pytest.mark.parametrize(
    ("first", "last", "outside"),
    [(5, 11, 30), (5, -1, 30), (-1, 11, 30), (2, 8, 0), (8, 11, 60), (9, 9, 60)],
)
def test_linear_threshold_crossings_include_hot_and_cold(first, last, outside):
    evidence = product_temperature(
        shipment([(0, first, 0), (60, last, 0)], arrival=60), material(), 60
    )
    assert evidence.observed_excursion_min == pytest.approx(outside)
    assert evidence.complete_journey
    assert evidence.unobserved_interval_min == 0
    assert not evidence.qa_release_authorized


def test_source_reported_total_does_not_drive_computed_status():
    hot = product_temperature(
        shipment([(0, 9, 0), (60, 9, 0)], arrival=60), material(budget=30), 60
    )
    assert hot.observed_excursion_min == 60
    assert hot.reported_excursion_min == 0
    assert hot.status == "OBSERVED_BUDGET_EXCEEDED"
    safe_samples = product_temperature(
        shipment([(0, 5, 900), (60, 5, 999)], arrival=60), material(), 60
    )
    assert safe_samples.reported_excursion_min == 999
    assert safe_samples.observed_excursion_min == 0
    assert safe_samples.status == "OBSERVED_WITHIN_BUDGET"


def test_long_gaps_are_unknown_without_temperature_extrapolation():
    evidence = product_temperature(
        shipment([(0, 5, 0), (30, 11, 0), (150, 11, 0), (180, 11, 0)], arrival=180),
        material(),
        60,
    )
    assert evidence.observed_excursion_min == pytest.approx(45)
    assert evidence.unobserved_interval_min == 120
    assert not evidence.complete_journey
    assert any("partial lower bound" in note for note in evidence.limitations)


def test_known_unsampled_journey_ends_are_reported_as_unobserved():
    evidence = product_temperature(
        shipment([(60, 9, 0), (120, 9, 0)], arrival=180), material(), 60
    )
    assert evidence.observed_excursion_min == 60
    assert evidence.unobserved_interval_min == 120
    assert not evidence.complete_journey


def test_in_transit_samples_do_not_invent_an_end_of_observation_interval():
    evidence = product_temperature(shipment([(0, 5, 0), (60, 5, 0)]), material(), 60)
    assert evidence.unobserved_interval_min == 0
    assert not evidence.complete_journey


@pytest.mark.parametrize("arrival,unobserved", [(None, 0), (60, 60)])
def test_missing_readings_never_report_zero_excursion(arrival, unobserved):
    evidence = product_temperature(shipment([], arrival=arrival), material(), 60)
    assert evidence.status == "UNAVAILABLE"
    assert evidence.observed_excursion_min is None
    assert evidence.reported_excursion_min is None
    assert evidence.last_product_c is None
    assert evidence.last_product_outside_range is None
    assert evidence.first_reading_at is None
    assert evidence.last_reading_at is None
    assert evidence.reading_count == 0
    assert evidence.unobserved_interval_min == unobserved
    assert not evidence.complete_journey
    assert not evidence.qa_release_authorized


@pytest.mark.parametrize("arrival", [None, 0, 60])
def test_one_outside_sample_is_a_temperature_fact_without_duration(arrival):
    evidence = product_temperature(
        shipment([(0, 9, 250)], arrival=arrival), material(), 60
    )
    assert evidence.last_product_outside_range
    assert evidence.observed_excursion_min is None
    assert evidence.status == "UNAVAILABLE"
    assert evidence.reported_excursion_min == 250
    assert not evidence.complete_journey
    assert any("One sample" in note for note in evidence.limitations)


@pytest.mark.parametrize("temperature", [5, 11])
def test_only_skipped_intervals_have_unknown_excursion(temperature):
    evidence = product_temperature(
        shipment([(0, temperature, 20), (120, temperature, 100)], arrival=120),
        material(),
        60,
    )
    assert evidence.status == "UNAVAILABLE"
    assert evidence.observed_excursion_min is None
    assert evidence.reported_excursion_min == 100
    assert evidence.reading_count == 2
    assert evidence.last_product_c == temperature
    assert evidence.unobserved_interval_min == 120
    assert not evidence.complete_journey


@pytest.mark.parametrize("gap", [0, -1, float("nan"), float("inf")])
def test_invalid_maximum_gap_is_rejected(gap):
    with pytest.raises(ValueError, match="finite and positive"):
        product_temperature(shipment([]), material(), gap)


def test_duplicate_sample_times_are_rejected():
    with pytest.raises(ValueError, match="strictly increasing sample times"):
        product_temperature(shipment([(0, 5, 0), (0, 10, 0)]), material(), 60)


def test_unordered_sample_times_are_rejected():
    with pytest.raises(ValueError, match="strictly increasing sample times"):
        product_temperature(shipment([(60, 5, 0), (0, 10, 0)]), material(), 60)


def test_budget_threshold_is_strictly_exceeded():
    evidence = product_temperature(
        shipment([(0, 9, 0), (60, 9, 0)], arrival=60), material(budget=60), 60
    )
    assert evidence.status == "OBSERVED_WITHIN_BUDGET"
