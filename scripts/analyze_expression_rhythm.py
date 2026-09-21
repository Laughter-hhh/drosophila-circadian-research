#!/usr/bin/env python3
"""Run descriptive fixed-period cosinor fits on probe-mapped expression samples.

The time basis must be declared explicitly; mixed ZT/CT rows are rejected.
For publication-grade inference use ``analyze_cosinor_inference.py`` with a
metadata join and an experimental-unit declaration.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_circadian_timeseries import analyze_rows


_TIME_RE = re.compile(r"\b(ZT|CT)\s*([+-]?\d+(?:\.\d+)?)", re.IGNORECASE)


def _normalize_time_system(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"ZT", "CT"}:
        raise ValueError("time_system must be ZT or CT")
    return normalized


def _time_hours(token: str, expected_system: str) -> float:
    match = _TIME_RE.search(token.strip())
    if not match:
        raise ValueError(f"cannot parse ZT/CT time token: {token}")
    observed_system = match.group(1).upper()
    if observed_system != expected_system:
        raise ValueError(f"time system mismatch: observed {observed_system}, expected {expected_system}")
    return float(match.group(2)) % 24.0


def analyze_expression_samples(path: Path, time_system: str = "unknown") -> list[dict[str, object]]:
    normalized_time_system = _normalize_time_system(time_system)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    required = {"gene_symbol", "sample_id", "cell_type", "time", "background", "expression"}
    if rows and not required.issubset(rows[0]):
        raise ValueError(f"sample expression CSV missing columns: {', '.join(sorted(required - set(rows[0])))}")
    rows_by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (row.get("gene_symbol", ""), row.get("cell_type", ""), row.get("background", ""))
        rows_by_group[key].append(row)
    output: list[dict[str, object]] = []
    for key in sorted(rows_by_group):
        gene, cell_type, background = key
        all_group_rows = rows_by_group[key]
        sample_ids = [(row.get("sample_id") or "").strip() for row in all_group_rows]
        if any(not sample_id for sample_id in sample_ids):
            raise ValueError(
                f"blank sample_id in gene/cell/background group {key}; "
                "each gene-level sample measurement needs a stable sample_id"
            )
        duplicate_sample_ids = sorted(
            sample_id for sample_id, count in Counter(sample_ids).items() if count > 1
        )
        if duplicate_sample_ids:
            preview = ", ".join(duplicate_sample_ids[:5])
            raise ValueError(
                f"duplicate sample_id within gene/cell/background group {key}: {preview}; "
                "aggregate probes/transcripts within each sample using an explicit "
                "gene-level rule before fitting; do not treat feature rows as replicates"
            )
        group = [row for row in all_group_rows if (row.get("expression") or "").strip()]
        if not group:
            output.append({"gene_symbol": gene, "cell_type": cell_type, "background": background, "status": "no_numeric_expression"})
            continue
        try:
            analysis_rows = [
                {"subject_id": row["sample_id"].strip(), "time_hours": str(_time_hours(row["time"], normalized_time_system)), "value": row["expression"]}
                for row in group
            ]
            result = analyze_rows(analysis_rows, period_hours=24.0, time_system=normalized_time_system)
            result.update({"gene_symbol": gene, "cell_type": cell_type, "background": background})
            output.append(result)
        except ValueError as exc:
            if "time system mismatch" in str(exc):
                raise
            output.append({
                "gene_symbol": gene,
                "cell_type": cell_type,
                "background": background,
                "status": "insufficient_or_invalid_time_series",
                "reason": str(exc),
                "n_observations": len(group),
                "n_unique_time_points": len({row.get("time", "") for row in group}),
                "time_system": normalized_time_system,
                "inference_warning": "No rhythm conclusion; at least four observations and three unique time points are required for the descriptive fit.",
            })
    return output


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-system", choices=("ZT", "CT"), required=True)
    args = parser.parse_args(argv[1:])
    try:
        result = analyze_expression_samples(args.input, args.time_system)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.write_text(json.dumps({"status": "exploratory_expression_rhythm", "time_system": args.time_system, "groups": result}, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
