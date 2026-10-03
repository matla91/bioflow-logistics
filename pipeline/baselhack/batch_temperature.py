"""Product-temperature evidence from samples, separate from ambient risk proxies."""

import math
from itertools import pairwise

from baselhack.interfaces import (
    BatchShipmentSnapshot,
    OperationalMaterial,
    ProductTemperatureEvidence,
)


def product_temperature(
    shipment: BatchShipmentSnapshot,
    material: OperationalMaterial,
    max_gap_min: float,
) -> ProductTemperatureEvidence:
    """Integrate sampled intervals without assuming a physical thermal response.

    Piecewise-linear interpolation is an explicit sampling assumption. Intervals
    with excessive gaps contribute no estimated excursion; they remain unknown.
    Source-reported cumulative excursion is retained but never drives this result.
    """
    if not math.isfinite(max_gap_min) or max_gap_min <= 0:
        raise ValueError("Maximum reading gap must be finite and positive")
    if shipment.material_id != material.id:
        raise ValueError("Shipment and temperature material must match")
    readings = shipment.readings
    if any(reading.shipment_id != shipment.id for reading in readings):
        raise ValueError("Product readings must belong to the assessed shipment")
    if any(first.at >= last.at for first, last in pairwise(readings)):
        raise ValueError("Product readings require strictly increasing sample times")
    if any(
        (shipment.actual_departure_at and reading.at < shipment.actual_departure_at)
        or (shipment.actual_arrival_at and reading.at > shipment.actual_arrival_at)
        for reading in readings
    ):
        raise ValueError("Product readings must fall within known actual milestones")

    limitations = [
        (
            f"Product-temperature excursion uses piecewise-linear interpolation only "
            f"between samples at most {max_gap_min:g} minutes apart; this sampling "
            "assumption does not infer a physical thermal response."
        ),
        (
            "No product temperature is extrapolated before the first or after the last "
            "reading. Unsampled intervals may contain additional excursion."
        ),
        (
            "Reported cumulative excursion is source evidence retained separately; "
            "it is not treated as a directly measured duration or used for this status."
        ),
        (
            "Material range and excursion budget are demonstration assumptions, not "
            "validated pharmaceutical QA release criteria. Human QA review is required "
            "for release; this assessment never authorizes it."
        ),
    ]
    common = {
        "shipment_id": shipment.id,
        "reading_count": len(readings),
        "range_c": material.range_c,
        "budget_min": material.budget_min,
        "qa_release_authorized": False,
    }
    if not readings:
        unobserved = (
            _minutes(shipment.actual_departure_at, shipment.actual_arrival_at)
            if shipment.actual_departure_at and shipment.actual_arrival_at
            else 0.0
        )
        return ProductTemperatureEvidence(
            **common,
            status="UNAVAILABLE",
            first_reading_at=None,
            last_reading_at=None,
            last_product_c=None,
            last_product_outside_range=None,
            observed_excursion_min=None,
            reported_excursion_min=None,
            unobserved_interval_min=unobserved,
            complete_journey=False,
            limitations=[
                (
                    "No product-temperature readings are available; excursion is unknown, "
                    "not zero. Unobserved minutes include only intervals bounded by "
                    "known actual milestones."
                ),
                *limitations,
            ],
        )

    excursion, unobserved, skipped, usable = 0.0, 0.0, 0, 0
    for first, last in pairwise(readings):
        duration = _minutes(first.at, last.at)
        if duration > max_gap_min:
            unobserved += duration
            skipped += 1
        else:
            usable += 1
            excursion += _outside_minutes(
                first.product_c, last.product_c, duration, material.range_c
            )
    first, last = readings[0], readings[-1]
    if shipment.actual_departure_at:
        unobserved += _minutes(shipment.actual_departure_at, first.at)
    if shipment.actual_arrival_at:
        unobserved += _minutes(last.at, shipment.actual_arrival_at)
    complete = bool(
        shipment.actual_departure_at
        and shipment.actual_arrival_at
        and first.at == shipment.actual_departure_at
        and last.at == shipment.actual_arrival_at
        and usable
        and not skipped
    )
    if skipped:
        limitations.append(
            f"{skipped} reading interval(s) exceed the maximum gap; their full "
            "duration is unobserved and contributes no estimated excursion."
        )
    if not complete:
        limitations.append(
            "The journey is not completely sampled. Computed excursion covers only "
            "usable intervals, a partial lower bound under the interpolation "
            "assumption; within-budget status does not establish whole-journey compliance."
        )
    if len(readings) == 1:
        limitations.append(
            "One sample establishes a temperature at one instant; no duration "
            "can be estimated from it."
        )
    if not usable:
        limitations.append(
            "No usable sampled interval is available; observed excursion duration "
            "is unknown, not zero. Individual temperatures and reported cumulative "
            "excursion remain source evidence."
        )
    return ProductTemperatureEvidence(
        **common,
        status="UNAVAILABLE"
        if not usable
        else "OBSERVED_BUDGET_EXCEEDED"
        if excursion > material.budget_min
        else "OBSERVED_WITHIN_BUDGET",
        first_reading_at=first.at,
        last_reading_at=last.at,
        last_product_c=last.product_c,
        last_product_outside_range=_outside(last.product_c, material.range_c),
        observed_excursion_min=excursion if usable else None,
        reported_excursion_min=last.excursion_min,
        unobserved_interval_min=unobserved,
        complete_journey=complete,
        limitations=limitations,
    )


def _minutes(start, end):
    return (end - start).total_seconds() / 60


def _outside(temperature, limits):
    return temperature < limits[0] or temperature > limits[1]


def _outside_minutes(first, last, duration, limits):
    """Partition a linear sample interval at exact crossings of either boundary."""
    cuts = [0.0, 1.0]
    if first != last:
        for boundary in limits:
            crossing = (boundary - first) / (last - first)
            if 0 < crossing < 1:
                cuts.append(crossing)
    cuts.sort()
    return duration * sum(
        end - start
        for start, end in pairwise(cuts)
        if _outside(first + (last - first) * (start + end) / 2, limits)
    )
