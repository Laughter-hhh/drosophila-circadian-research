#!/usr/bin/env python3
"""Split a mixed-model input table into deterministic analysis-stratum files.

The splitter preserves rows and columns. It does not infer metadata, aggregate
observations or fit a model; each output still needs the formal preparation gate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

REQUIRED_STRATUM_COLUMNS = ["gene_symbol", "cell_type", "background"]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized).strip("._-")
    return normalized or "missing"


def _filename(key: tuple[str, str, str]) -> str:
    readable = "__".join(_slug(item) for item in key)
    digest = hashlib.sha256("\x1f".join(key).encode("utf-8")).hexdigest()[:10]
    return f"{readable}__{digest}.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size_bytes": int(stat.st_size), "sha256": _sha256(path)}


def split(input_path: Path, output_dir: Path, manifest_path: Path) -> dict[str, object]:
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        input_columns = list(reader.fieldnames or [])
        missing_columns = [column for column in REQUIRED_STRATUM_COLUMNS if column not in input_columns]
        if missing_columns:
            raise ValueError("input is missing analysis-stratum columns: " + ", ".join(missing_columns))
        rows = list(reader)

    if not rows:
        raise ValueError("input CSV is empty")
    missing_values = sorted({column for row in rows for column in REQUIRED_STRATUM_COLUMNS if not _clean(row.get(column))})
    if missing_values:
        raise ValueError("analysis-stratum values are missing in column(s): " + ", ".join(missing_values))

    input_metadata = _file_metadata(input_path)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        key = tuple(_clean(row.get(column)) for column in REQUIRED_STRATUM_COLUMNS)
        grouped.setdefault(key, []).append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    stratum_records: list[dict[str, object]] = []
    used_names: set[str] = set()
    for key in sorted(grouped):
        filename = _filename(key)
        if filename in used_names:
            raise ValueError(f"deterministic output filename collision for stratum: {key}")
        used_names.add(filename)
        output_path = output_dir / filename
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=input_columns, extrasaction="raise")
            writer.writeheader()
            writer.writerows(grouped[key])
        stratum_records.append({
            "gene_symbol": key[0],
            "cell_type": key[1],
            "background": key[2],
            "n_rows": len(grouped[key]),
            "output_file": str(output_path),
            "sha256": _sha256(output_path),
        })

    result = {
        "status": "split_ready" if len(stratum_records) > 1 else "single_stratum_no_split_needed",
        "input_file": str(input_path),
        "input_file_metadata": input_metadata,
        "output_dir": str(output_dir),
        "manifest_file": str(manifest_path),
        "input_columns": input_columns,
        "n_raw_rows": len(rows),
        "n_analysis_strata": len(stratum_records),
        "row_conservation": {
            "input_rows": len(rows),
            "output_rows": sum(int(record["n_rows"]) for record in stratum_records),
            "exact": sum(int(record["n_rows"]) for record in stratum_records) == len(rows),
        },
        "strata": stratum_records,
        "next_step": "Run prepare_mixed_model_input.py separately on each output_file; this splitter does not validate metadata or fit a model.",
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    try:
        result = split(args.input, args.output_dir, args.output_manifest)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({key: result[key] for key in ["status", "n_raw_rows", "n_analysis_strata", "row_conservation"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
