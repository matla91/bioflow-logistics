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
from baselhack.output import dumps, dumps_frontend, write, write_frontend
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


def load_demo(name, observations_path=None):
    """Load a named simulated state and explicit overrides of the shared assumptions."""
    if name not in {"normal", "disruption", "severe"}:
        raise ValueError("Choose normal, disruption or severe")
    observations, shipment, assumptions = load_inputs(
        observations_path or ROOT / "data/cache/logistics_basel.json",
        ROOT / "scenarios/logistics" / f"{name}.json",
        ROOT / "config/logistics.yaml",
    )
    overrides = yaml.safe_load(
        (ROOT / "config/logistics_scenarios" / f"{name}.yaml").read_text()
    )
    assumptions = LogisticsAssumptions.model_validate(
        {**assumptions.model_dump(mode="python"), **overrides}
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
    parser.add_argument("--scenario", choices=["normal", "disruption", "severe"])
    parser.add_argument(
        "--detailed",
        action="store_true",
        help="Export internal features, assumptions and full source metadata",
    )
    parser.add_argument(
        "--observations", type=Path, default=ROOT / "data/cache/logistics_basel.json"
    )
    parser.add_argument("--shipment", type=Path)
    parser.add_argument("--assumptions", type=Path)
    parser.add_argument("--stations", nargs="+", default=["402"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            if args.scenario and (args.shipment or args.assumptions):
                parser.error("Use --scenario or custom --shipment/--assumptions paths")
            inputs = (
                load_demo(args.scenario, args.observations)
                if args.scenario
                else load_inputs(
                    args.observations,
                    args.shipment or ROOT / "scenarios/logistics_demo.json",
                    args.assumptions or ROOT / "config/logistics.yaml",
                )
            )
            result = evaluate(*inputs, args.stations)
            if args.output:
                if args.detailed:
                    write(result, args.output)
                else:
                    write_frontend(result, args.output)
            else:
                sys.stdout.write(
                    dumps(result) if args.detailed else dumps_frontend(result)
                )
        else:
            if args.scenario or args.detailed:
                parser.error("--scenario and --detailed apply only to demo output")
            shipment_path = args.shipment or ROOT / "scenarios/logistics_demo.json"
            assumptions_path = args.assumptions or ROOT / "config/logistics.yaml"
            shipment = ShipmentState.model_validate_json(shipment_path.read_text())
            assumptions = LogisticsAssumptions.model_validate(
                yaml.safe_load(assumptions_path.read_text())
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
