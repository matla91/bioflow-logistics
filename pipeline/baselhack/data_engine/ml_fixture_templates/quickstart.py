"""Load observable features separately from synthetic targets; optionally fit a baseline."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

TARGETS = (
    "synthetic_ready_by_deadline",
    "incoming_all_on_time",
    "synthetic_final_excursion_exceeded",
)


def load(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    for name, info in manifest["files"].items():
        assert (
            hashlib.sha256((folder / name).read_bytes()).hexdigest() == info["sha256"]
        ), name
    with (folder / "features.csv").open(newline="") as stream:
        features = {r["batch_id"]: r for r in csv.DictReader(stream)}
    with (folder / "labels.csv").open(newline="") as stream:
        labels = list(csv.DictReader(stream))
    with (folder / "case_index.csv").open(newline="") as stream:
        metadata = {r["batch_id"]: r for r in csv.DictReader(stream)}
    columns = manifest["feature_columns"]
    assert len(features) == len(labels) == len(metadata)
    groups = {}
    data = {
        split: {"X": [], "y": {target: [] for target in TARGETS}}
        for split in ("train", "validation", "test")
    }
    for row in labels:
        meta = metadata[row["batch_id"]]
        assert meta["split"] == row["split"]
        assert groups.setdefault(meta["group_id"], row["split"]) == row["split"]
        split = data[row["split"]]
        observed = features[row["batch_id"]]
        split["X"].append(
            [float(observed[c]) if observed[c] else float("nan") for c in columns]
        )
        for target in TARGETS:
            split["y"][target].append(int(row[target]))
    return data


def scores(truth, probabilities):
    predicted = [int(p >= 0.5) for p in probabilities]
    accuracy = sum(a == b for a, b in zip(truth, predicted, strict=True)) / len(truth)
    recalls = [
        sum(a == b == cls for a, b in zip(truth, predicted, strict=True))
        / truth.count(cls)
        for cls in (0, 1)
        if cls in truth
    ]
    return {
        "accuracy": round(accuracy, 4),
        "balanced_accuracy": round(sum(recalls) / len(recalls), 4),
        "brier": round(
            sum((y - p) ** 2 for y, p in zip(truth, probabilities, strict=True))
            / len(truth),
            4,
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fit", action="store_true")
    args = parser.parse_args()
    data = load(Path(__file__).resolve().parent)
    print("All package checksums and group splits validated")
    print({key: len(value["X"]) for key, value in data.items()})
    for target in TARGETS:
        train = data["train"]["y"][target]
        prevalence = sum(train) / len(train)
        test = data["test"]["y"][target]
        print(
            target,
            "test classes",
            dict(Counter(test)),
            "constant baseline",
            scores(test, [prevalence] * len(test)),
        )
        if args.fit:
            from sklearn.ensemble import HistGradientBoostingClassifier

            model = HistGradientBoostingClassifier(
                max_iter=50, max_leaf_nodes=8, random_state=20261003
            )
            model.fit(data["train"]["X"], train)
            print(
                "synthetic fitted baseline",
                scores(test, model.predict_proba(data["test"]["X"])[:, 1].tolist()),
            )
    print("Synthetic generator evaluation only; not validated real-world performance.")


if __name__ == "__main__":
    main()
