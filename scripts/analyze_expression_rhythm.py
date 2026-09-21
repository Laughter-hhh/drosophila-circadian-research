#!/usr/bin/env python3
"""Run descriptive fixed-period cosinor fits on probe-mapped expression samples.

The time basis must be declared explicitly; mixed ZT/CT rows are rejected.
When present, timecourse_id is a grouping stratum and is never pooled.
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


_MISSING_CONTEXT = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NOT_AVAILABLE", "NOT AVAILABLE", "NOT APPLICABLE", "NONE REPORTED", "."}


def _context_value(row: dict[str, str], names: tuple[str, ...]) -> str:
    for name in names:
        value = (row.get(name) or "").strip()
        if value and value.upper() not in _MISSING_CONTEXT:
            return value
    return "unknown"


def analyze_expression_samples(path: Path, time_system: str = "unknown") -> list[dict[str, object]]:
    normalized_time_system = _normalize_time_system(time_system)
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    has_timecourse_column = bool(rows and "timecourse_id" in rows[0])
    required = {"gene_symbol", "sample_id", "cell_type", "time", "background", "expression"}
    if rows and not required.issubset(rows[0]):
        raise ValueError(f"sample expression CSV missing columns: {', '.join(sorted(required - set(rows[0])))}")
    rows_by_group: dict[tuple[str, str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    context_by_sample: dict[str, tuple[str, str]] = {}
    for row in rows:
        sample_id = (row.get("sample_id") or "").strip()
        developmental_stage = _context_value(row, ("developmental_stage", "developmental stage", "stage"))
        sex = _context_value(row, ("sex", "gender"))
        timecourse_id = _context_value(row, ("timecourse_id", "timecourse"))
        if sample_id:
            sample_context = (developmental_stage, sex)
            previous_context = context_by_sample.setdefault(sample_id, sample_context)
            if previous_context != sample_context:
                raise ValueError(
                    f"conflicting sex/developmental_stage metadata for sample_id {sample_id}: "
                    f"{previous_context} vs {sample_context}"
                )
        key = (
            row.get("gene_symbol", ""),
            row.get("cell_type", ""),
            row.get("background", ""),
            developmental_stage,
            sex,
            timecourse_id,
        )
        rows_by_group[key].append(row)
    output: list[dict[str, object]] = []
    for key in sorted(rows_by_group):
        gene, cell_type, background, developmental_stage, sex, timecourse_id = key
        all_group_rows = rows_by_group[key]
        sample_ids = [(row.get("sample_id") or "").strip() for row in all_group_rows]
        if any(not sample_id for sample_id in sample_ids):
            raise ValueError(
                f"blank sample_id in gene/cell/background/stage/sex/timecourse group {key}; "
                "each gene-level sample measurement needs a stable sample_id"
            )
        duplicate_sample_ids = sorted(
            sample_id for sample_id, count in Counter(sample_ids).items() if count > 1
        )
        if duplicate_sample_ids:
            preview = ", ".join(duplicate_sample_ids[:5])
            raise ValueError(
                f"duplicate sample_id within gene/cell/background/stage/sex/timecourse group {key}: {preview}; "
                "aggregate probes/transcripts within each sample using an explicit "
                "gene-level rule before fitting; do not treat feature rows as replicates"
            )
        group = [row for row in all_group_rows if (row.get("expression") or "").strip()]
        if not group:
            record: dict[str, object] = {
                "gene_symbol": gene,
                "cell_type": cell_type,
                "background": background,
                "developmental_stage": developmental_stage,
                "sex": sex,
                "status": "no_numeric_expression",
            }
            if has_timecourse_column:
                record["timecourse_id"] = timecourse_id
            output.append(record)
            continue
        try:
            analysis_rows = [
                {
                    "subject_id": row["sample_id"].strip(),
                    "time_hours": str(_time_hours(row["time"], normalized_time_system)),
                    "value": row["expression"],
                }
                for row in group
            ]
            result = analyze_rows(analysis_rows, period_hours=24.0, time_system=normalized_time_system)
            result.update({
                "gene_symbol": gene,
                "cell_type": cell_type,
                "background": background,
                "developmental_stage": developmental_stage,
                "sex": sex,
            })
            if has_timecourse_column:
                result.update({
                    "timecourse_id": timecourse_id,
                    "replication_unit_warning": "n_subjects counts sample_id values, which may be pooled libraries; it does not establish the number of independent flies.",
                })
            output.append(result)
        except ValueError as exc:
            if "time system mismatch" in str(exc):
                raise
            record = {
                "gene_symbol": gene,
                "cell_type": cell_type,
                "background": background,
                "developmental_stage": developmental_stage,
                "sex": sex,
                "status": "insufficient_or_invalid_time_series",
                "reason": str(exc),
                "n_observations": len(group),
                "n_unique_time_points": len({row.get("time", "") for row in group}),
                "time_system": normalized_time_system,
                "inference_warning": "No rhythm conclusion; at least four observations and three unique time points are required for the descriptive fit.",
            }
            if has_timecourse_column:
                record.update({
                    "timecourse_id": timecourse_id,
                    "replication_unit_warning": "n_observations count sample_id values, which may be pooled libraries; they do not establish the number of independent flies.",
                })
            output.append(record)
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
