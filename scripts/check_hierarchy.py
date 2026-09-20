#!/usr/bin/env python3
"""Check biological-replicate nesting and batch/time confounding in CSV data."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


def inspect(path: Path, time_field: str = "ZT_or_CT") -> dict[str, object]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header")
        required = {"biological_replicate_id", "batch_id", time_field}
        missing = sorted(required.difference(reader.fieldnames))
        if missing:
            raise ValueError("missing required column(s): " + ", ".join(missing))
        rows = list(reader)
    if not rows:
        raise ValueError("CSV contains no data rows")

    replicate_counts: dict[str, int] = defaultdict(int)
    batch_times: dict[str, set[str]] = defaultdict(set)
    time_batches: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        replicate = (row.get("biological_replicate_id") or "").strip()
        batch = (row.get("batch_id") or "").strip()
        time = (row.get(time_field) or "").strip()
        if not replicate or not batch or not time:
            raise ValueError("biological_replicate_id, batch_id and time fields cannot be blank")
        replicate_counts[replicate] += 1
        batch_times[batch].add(time)
        time_batches[time].add(batch)

    repeated = {key: count for key, count in replicate_counts.items() if count > 1}
    perfectly_confounded = bool(batch_times) and all(len(times) == 1 for times in batch_times.values()) and all(len(batches) == 1 for batches in time_batches.values())
    status = "warning" if perfectly_confounded or repeated else "ok"
    warnings: list[str] = []
    if repeated:
        warnings.append("multiple observations share a biological_replicate_id; model or summarize the hierarchy")
    if perfectly_confounded:
        warnings.append("batch_id and time are perfectly confounded in this table")
    return {
        "status": status,
        "n_rows": len(rows),
        "n_biological_replicates": len(replicate_counts),
        "observations_per_replicate": dict(sorted(replicate_counts.items())),
        "batch_to_time": {key: sorted(value) for key, value in sorted(batch_times.items())},
        "time_to_batch": {key: sorted(value) for key, value in sorted(time_batches.items())},
        "repeated_biological_replicates": repeated,
        "warnings": warnings,
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--time-field", default="ZT_or_CT")
    args = parser.parse_args(argv[1:])
    try:
        result = inspect(args.input, args.time_field)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
