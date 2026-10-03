"""Initialize, collect, seed and export the centralized data store."""

import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path

from baselhack.interfaces import RealObservations
from baselhack.storage import ROOT, canonical, read_yaml

from .database import Database
from .ingest import import_observations, ingest_once
from .operations import generate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database", type=Path, default=ROOT / ".runtime/current-affairs.sqlite3"
    )
    parser.add_argument("--config", default="config/data_engine.yaml")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init")
    ingestion = subcommands.add_parser("ingest")
    ingestion.add_argument("--start", type=datetime.fromisoformat)
    ingestion.add_argument("--end", type=datetime.fromisoformat)
    watch = subcommands.add_parser("watch")
    watch.add_argument("--cycles", type=int, help="Optional finite number of cycles")
    seed = subcommands.add_parser("seed")
    seed.add_argument("--settings", default="config/operations_demo.yaml")
    seed.add_argument("--output", type=Path)
    cache = subcommands.add_parser("import-cache")
    cache.add_argument(
        "--input", type=Path, default=ROOT / "data/cache/logistics_basel.json"
    )
    export = subcommands.add_parser("export-observations")
    export.add_argument("--as-of", type=datetime.fromisoformat, required=True)
    export.add_argument("--known-at", type=datetime.fromisoformat)
    export.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    database = Database(args.database)
    try:
        database.initialize()
        if args.command == "init":
            print(f"Initialized {args.database}")
        elif args.command == "seed":
            dataset = generate(read_yaml(args.settings))
            inserted = database.store_operations(dataset)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    canonical(dataset.model_dump(mode="json")) + "\n"
                )
            print(
                json.dumps(
                    {
                        "dataset_id": dataset.dataset_id,
                        "inserted": inserted,
                        "shipments": len(dataset.shipments),
                        "batches": len(dataset.batches),
                        "readings": len(dataset.readings),
                    }
                )
            )
        elif args.command == "import-cache":
            with database.collector_lock():
                print(
                    json.dumps(
                        import_observations(
                            database,
                            RealObservations.model_validate_json(
                                args.input.read_text()
                            ),
                        )
                    )
                )
        elif args.command == "export-observations":
            observations = database.observations(args.as_of, args.known_at)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(observations.model_dump_json(indent=2) + "\n")
            print(f"Exported stored observations to {args.output}")
        else:
            settings = read_yaml(args.config)
            if settings["poll_interval_min"] <= 0:
                raise ValueError("Polling interval must be positive")
            if args.command == "watch" and args.cycles is not None and args.cycles < 1:
                raise ValueError("Cycle count must be positive")
            cycles = 0
            while True:
                with database.collector_lock():
                    reports = ingest_once(
                        database,
                        settings,
                        start=args.start if args.command == "ingest" else None,
                        end=args.end if args.command == "ingest" else None,
                    )
                print(json.dumps(reports), flush=True)
                cycles += 1
                if (
                    args.command == "ingest"
                    or args.cycles is not None
                    and cycles >= args.cycles
                ):
                    return 0 if all(r["status"] == "success" for r in reports) else 1
                time.sleep(settings["poll_interval_min"] * 60)
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as error:
        print(f"Data engine: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
