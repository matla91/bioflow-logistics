"""Reproducible snapshot risk CLI, separate from the existing journey demo."""

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import yaml

from baselhack.features import build_features
from baselhack.interfaces import (
    LogisticsAssumptions,
    LogisticsResult,
    RealObservations,
    ShipmentState,
)
from baselhack.output import dumps, write
from baselhack.simulation import simulate
from baselhack.storage import ROOT


def evaluate(
    observations: RealObservations,
    shipment: ShipmentState,
    assumptions: LogisticsAssumptions,
    station_ids: list[str],
) -> LogisticsResult:
    """Combine observed features with simulated shipment state at a fixed cutoff."""
    features = build_features(observations, shipment.as_of, assumptions, station_ids)
    return simulate(shipment, features, assumptions, observations.sources)


def load_inputs(observations_path, shipment_path, assumptions_path):
    observations = RealObservations.model_validate_json(
        Path(observations_path).read_text(encoding="utf-8")
    )
    shipment = ShipmentState.model_validate_json(
        Path(shipment_path).read_text(encoding="utf-8")
    )
    assumptions = LogisticsAssumptions.model_validate(
        yaml.safe_load(Path(assumptions_path).read_text(encoding="utf-8"))
    )
    return observations, shipment, assumptions


def refresh(shipment, assumptions, station_ids):
    """Fetch bounded real history; failures never substitute simulated observations."""
    from baselhack.ingestion import rhine, traffic, weather

    end = shipment.as_of
    traffic_rows, traffic_source = traffic.download(
        end - timedelta(weeks=13), end, stations=station_ids
    )
    trend_start = end - timedelta(minutes=assumptions.trend_window_min)
    rhine_rows, rhine_source = rhine.download(trend_start, end)
    weather_rows, weather_source = weather.download(trend_start, end)
    return RealObservations(
        traffic=traffic_rows,
        rhine=rhine_rows,
        weather=weather_rows,
        sources=[traffic_source, rhine_source, weather_source],
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["demo", "fetch"])
    parser.add_argument(
        "--observations", type=Path, default=ROOT / "data/cache/logistics_basel.json"
    )
    parser.add_argument(
        "--shipment", type=Path, default=ROOT / "scenarios/logistics_demo.json"
    )
    parser.add_argument(
        "--assumptions", type=Path, default=ROOT / "config/logistics.yaml"
    )
    parser.add_argument("--stations", nargs="+", default=["402"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            inputs = load_inputs(args.observations, args.shipment, args.assumptions)
            result = evaluate(*inputs, args.stations)
            if args.output:
                write(result, args.output)
            else:
                sys.stdout.write(dumps(result))
        else:
            shipment = ShipmentState.model_validate_json(args.shipment.read_text())
            assumptions = LogisticsAssumptions.model_validate(
                yaml.safe_load(args.assumptions.read_text())
            )
            if args.output is None:
                parser.error(
                    "fetch requires --output pointing to a new observations file"
                )
            if args.output.exists():
                raise ValueError(
                    "Choose a new output path; existing evidence is preserved"
                )
            observations = refresh(shipment, assumptions, args.stations)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(
                    observations.model_dump(mode="json"),
                    indent=2,
                    sort_keys=True,
                    allow_nan=False,
                )
                + "\n",
                encoding="utf-8",
            )
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Logistics layer: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
