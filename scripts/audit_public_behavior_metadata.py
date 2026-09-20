#!/usr/bin/env python3
"""Audit a downloaded public Drosophila behavior metadata table before raw-data retrieval.

This tool intentionally does not infer genotype, sex, age, temperature, lighting
schedule, raw behavior values, or circadian conclusions from a repository index.
It verifies a known ethoscope metadata layout and explicitly reports what is
still required before downloading or analysing large raw recordings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path


REQUIRED_COLUMNS = ("machine_name", "date", "region_id", "condition", "Run", "reversed", "lux", "baseline_days")
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED", "."}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _present(value: object) -> bool:
    return str(value or "").strip().upper() not in MISSING


def audit(path: Path, source_url: str, expected_sha256: str | None = None, provenance_path: str | None = None) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        issues.append({"type": "missing_expected_ethoscope_metadata_columns", "columns": missing})
    observed_hash = _sha256(path)
    if expected_sha256:
        normalized = expected_sha256.lower()
        if not SHA_RE.fullmatch(normalized):
            issues.append({"type": "invalid_expected_sha256"})
        elif normalized != observed_hash:
            issues.append({"type": "input_sha256_mismatch", "expected": normalized, "observed": observed_hash})
    invalid_rows: list[dict[str, object]] = []
    keys: set[tuple[str, str, str]] = set()
    duplicate_keys: set[tuple[str, str, str]] = set()
    condition_counts: Counter[str] = Counter()
    for line, row in enumerate(rows, start=2):
        values = {column: (row.get(column) or "").strip() for column in REQUIRED_COLUMNS}
        absent = [column for column, value in values.items() if not _present(value)]
        if absent:
            invalid_rows.append({"line": line, "type": "missing_metadata_value", "columns": absent})
            continue
        key = (values["machine_name"], values["date"], values["region_id"])
        if key in keys:
            duplicate_keys.add(key)
        keys.add(key)
        condition_counts[values["condition"]] += 1
        try:
            float(values["lux"])
            float(values["baseline_days"])
        except ValueError:
            invalid_rows.append({"line": line, "type": "non_numeric_lux_or_baseline_days"})
    if duplicate_keys:
        issues.append({"type": "duplicate_machine_date_region_id", "n_duplicates": len(duplicate_keys)})
    issues.extend(invalid_rows)
    status = "verified_public_behavior_metadata_audit" if rows and not issues else "blocked_public_behavior_metadata_audit"
    return {
        "status": status,
        "analysis_readiness": "blocked_metadata_insufficient_for_behavior_analysis",
        "source_url": source_url,
        "input_file_metadata": {"path": provenance_path or str(path), "size_bytes": path.stat().st_size, "sha256": observed_hash},
        "n_rows": len(rows),
        "n_machine_date_region_keys": len(keys),
        "condition_counts": dict(sorted(condition_counts.items())),
        "observed_columns": fieldnames,
        "required_columns": list(REQUIRED_COLUMNS),
        "missing_research_metadata": [
            "species confirmation in the local table", "genotype/strain", "sex", "age_days",
            "temperature_C", "LD/DD timing definition", "individual fly identifier validation",
            "raw ethoscope recording files and their checksums",
        ],
        "issues": issues,
        "inference_warning": "A passing audit only verifies the downloaded repository metadata layout and hash. It does not retrieve raw recordings, establish that each region is an analyzable fly, or support behavior, circadian, neural or causal conclusions.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provenance-path", help="Portable path recorded in the audit report.")
    args = parser.parse_args(argv[1:])
    try:
        result = audit(args.input, args.source_url, args.expected_sha256, args.provenance_path)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_public_behavior_metadata_audit" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))



