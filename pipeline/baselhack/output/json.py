"""Stable, validated JSON output with all evidence and simulation assumptions."""

import json
from pathlib import Path

from baselhack.interfaces import LogisticsResult


def dumps(result: LogisticsResult) -> str:
    """Serialize probabilities and provenance without non-finite JSON numbers."""
    # Revalidate copied/mutated model instances as plain values at the boundary.
    validated = LogisticsResult.model_validate(result.model_dump(mode="python"))
    return (
        json.dumps(
            validated.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n"
    )


def write(result: LogisticsResult, path: str | Path) -> Path:
    """Save a reviewable JSON artifact; callers choose its destination."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps(result), encoding="utf-8")
    return target
