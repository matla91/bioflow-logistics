"""Export the canonical synthetic fixture into linked JSON/CSV tables."""

import csv
import hashlib
import io
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "output/operations-demo.json"
DESTINATION = ROOT / "data/examples/operations"
TABLES = {
    "materials": "materials",
    "shipments": "shipments",
    "batches": "batches",
    "batch_supply_plans": "supply_plans",
    "inventory_lots": "inventory",
    "stock_reservations": "reservations",
    "shipment_readings": "readings",
}


def csv_value(value):
    if value is None:
        return ""
    if isinstance(value, (list, dict, bool)):
        return json.dumps(value, separators=(",", ":"))
    return value


def main():
    dataset = json.loads(SOURCE.read_text())
    if dataset.get("simulated") is not True:
        raise ValueError("Only explicitly simulated operational data may be exported")
    DESTINATION.mkdir(parents=True, exist_ok=True)
    manifest = {
        "dataset_id": dataset["dataset_id"],
        "simulated": True,
        "seed": dataset["seed"],
        "reference_at": dataset["reference_at"],
        "source": str(SOURCE.relative_to(ROOT)),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "files": {},
    }
    for filename, key in TABLES.items():
        records = dataset[key]
        fields = list(dict.fromkeys(field for row in records for field in row))
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(
            {field: csv_value(row.get(field)) for field in fields} for row in records
        )
        contents = {
            f"{filename}.json": json.dumps(records, indent=2, ensure_ascii=False)
            + "\n",
            f"{filename}.csv": buffer.getvalue(),
        }
        for name, content in contents.items():
            payload = content.encode("utf-8")
            (DESTINATION / name).write_bytes(payload)
            manifest["files"][name] = {
                "records": len(records),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
    (DESTINATION / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({name: len(dataset[key]) for name, key in TABLES.items()}))


if __name__ == "__main__":
    main()
