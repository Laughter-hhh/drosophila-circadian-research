#!/usr/bin/env python3
"""Exploratory cosinor inference with metadata and biological-unit gates.

This helper is intentionally exploratory. It requires an explicit ``ZT`` or
``CT`` declaration, validates that labelled time tokens use the same basis,
and refuses to turn repeated technical/biological observations into
independent rows. It does not replace a pre-specified mixed-effects model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.analyze_circadian_timeseries import analyze_rows


TIME_RE = re.compile(r"\b(ZT|CT)\s*([+-]?\d+(?:\.\d+)?)\b", re.IGNORECASE)
DIRECT_REQUIRED = {"subject_id", "time_hours", "value"}
EXPRESSION_REQUIRED = {"sample_id", "time", "expression"}
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NOT_AVAILABLE", "NOT AVAILABLE", "NOT APPLICABLE", "NONE REPORTED", "."}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_metadata(path: Path) -> dict[str, object]:
    stat = path.stat()
    return {"path": str(path), "size_bytes": int(stat.st_size), "sha256": _sha256(path)}


def _normalize_time_system(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    if normalized in {"", "UNKNOWN", "UNSPECIFIED"}:
        return ""
    if normalized not in {"ZT", "CT"}:
        raise ValueError("time_system must be ZT or CT")
    return normalized


def _time_token(token: str, expected_system: str | None = None) -> tuple[float, str]:
    match = TIME_RE.search(token.strip())
    if not match:
        raise ValueError(f"cannot parse ZT/CT time token: {token}")
    basis = match.group(1).upper()
    expected = _normalize_time_system(expected_system)
    if expected and basis != expected:
        raise ValueError(f"time system mismatch: expected {expected}, observed {basis} in {token!r}")
    value = float(match.group(2))
    if not math.isfinite(value):
        raise ValueError(f"time token is nonfinite: {token}")
    return value % 24.0, basis


def _time_hours(token: str, expected_system: str | None = None) -> float:
    return _time_token(token, expected_system)[0]


def _bh_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    order = sorted(range(len(p_values)), key=lambda idx: p_values[idx])
    adjusted = [1.0] * len(p_values)
    running = 1.0
    m = len(p_values)
    for rank, idx in reversed(list(enumerate(order, start=1))):
        running = min(running, p_values[idx] * m / rank)
        adjusted[idx] = min(1.0, running)
    return adjusted


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _load_metadata(path: Path, time_system: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if "sample_id" not in set(reader.fieldnames or []):
            raise ValueError("metadata file needs sample_id column")
        metadata: dict[str, dict[str, str]] = {}
        for row in reader:
            sample_id = (row.get("sample_id") or "").strip()
            if not sample_id:
                continue
            if sample_id in metadata:
                raise ValueError(f"duplicate sample_id in metadata: {sample_id}")
            metadata[sample_id] = row
            metadata_time = (row.get("ZT_or_CT") or row.get("time") or "").strip()
            if metadata_time:
                _time_token(metadata_time, time_system)
    if not metadata:
        raise ValueError("metadata file contains no sample rows")
    return metadata


def _context_value(row: dict[str, str], aliases: tuple[str, ...]) -> str:
    for name in aliases:
        value = (row.get(name) or "").strip()
        if _present(value):
            return value
    return "unknown"


def _context_match_key(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").split())


def _joined_context(data_row: dict[str, str], metadata_row: dict[str, str], label: str, aliases: tuple[str, ...]) -> str:
    data_value = _context_value(data_row, aliases)
    metadata_value = _context_value(metadata_row, aliases)
    if data_value != "unknown" and metadata_value != "unknown" and _context_match_key(data_value) != _context_match_key(metadata_value):
        sample_id = (data_row.get("sample_id") or data_row.get("subject_id") or "").strip()
        raise ValueError(
            f"{label} mismatch between expression data and metadata for sample_id "
            f"{sample_id}: {data_value!r} vs {metadata_value!r}"
        )
    return data_value if data_value != "unknown" else metadata_value


def _load_groups(path: Path, metadata_path: Path | None = None, declared_unit: str | None = None, time_system: str = "ZT") -> tuple[dict[tuple[str, str, str, str, str], list[dict[str, object]]], list[dict[str, str]], bool]:
    metadata = _load_metadata(metadata_path, time_system) if metadata_path else {}
    metadata_warnings: list[dict[str, str]] = []
    warning_counts: dict[str, int] = defaultdict(int)
    declared_unit_clean = (declared_unit or "").strip()
    if not _present(declared_unit_clean):
        declared_unit_clean = ""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        if DIRECT_REQUIRED.issubset(fieldnames):
            mode = "direct"
        elif EXPRESSION_REQUIRED.issubset(fieldnames):
            mode = "expression"
        else:
            raise ValueError("input needs subject_id,time_hours,value or sample_id,time,expression columns")
        groups: dict[tuple[str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)
        context_by_sample: dict[str, tuple[str, str]] = {}
        for row_index, row in enumerate(reader, start=2):
            if mode == "expression" and not (row.get("expression") or "").strip():
                continue
            try:
                if mode == "direct":
                    sample_or_subject = str(row["subject_id"])
                    time_hours = float(row["time_hours"])
                    value = float(row["value"])
                else:
                    sample_or_subject = str(row["sample_id"])
                    time_hours = _time_hours(row["time"], time_system)
                    value = float(row["expression"])
                if not math.isfinite(time_hours) or not math.isfinite(value):
                    raise ValueError("time_hours/value must be finite")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid numeric/time row {row_index}: {row}") from exc
            subject_id = sample_or_subject
            unit = (row.get("experimental_unit") or "").strip() or declared_unit_clean
            if not _present(unit):
                unit = ""
            metadata_row: dict[str, str] = {}
            if metadata_path:
                metadata_row = metadata.get(sample_or_subject) or {}
                if not metadata_row:
                    raise ValueError(f"sample_id missing from metadata: {sample_or_subject}")
                metadata_time = (metadata_row.get("ZT_or_CT") or metadata_row.get("time") or "").strip()
                if metadata_time:
                    metadata_time_hours = _time_hours(metadata_time, time_system)
                    if abs(metadata_time_hours - time_hours) > 1e-9:
                        raise ValueError(f"time mismatch between data and metadata for {sample_or_subject}: {time_hours} vs {metadata_time_hours}")
                unit = (metadata_row.get("experimental_unit") or "").strip() or unit
                if not _present(unit):
                    unit = ""
                subject_id = (metadata_row.get("biological_replicate_id") or "").strip() or sample_or_subject
                if not _present(metadata_row.get("experimental_unit")):
                    warning_counts["missing_experimental_unit"] += 1
                if not _present(metadata_row.get("batch_id")):
                    warning_counts["unknown_batch"] += 1
                if not _present(metadata_row.get("temperature_C")):
                    warning_counts["unknown_temperature"] += 1
            developmental_stage = _joined_context(
                row, metadata_row, "developmental_stage",
                ("developmental_stage", "developmental stage", "stage"),
            )
            sex = _joined_context(row, metadata_row, "sex", ("sex", "gender"))
            sample_context = (developmental_stage, sex)
            previous_context = context_by_sample.setdefault(sample_or_subject, sample_context)
            if previous_context != sample_context:
                raise ValueError(
                    f"conflicting sex/developmental_stage metadata for sample_id {sample_or_subject}: "
                    f"{previous_context} vs {sample_context}"
                )
            key = (
                (row.get("gene_symbol") or "").strip(),
                (row.get("cell_type") or "").strip(),
                (row.get("background") or "").strip(),
                developmental_stage,
                sex,
            )
            groups[key].append({
                "subject_id": subject_id,
                "time_hours": time_hours,
                "value": value,
                "experimental_unit": unit,
            })
    metadata_warnings = [{"type": key, "n_rows": str(value)} for key, value in sorted(warning_counts.items())]
    return dict(groups), metadata_warnings, bool(metadata_path)


def _fit(rows: list[dict[str, object]], time_system: str) -> dict[str, object]:
    return analyze_rows(
        [{"subject_id": str(row["subject_id"]), "time_hours": str(row["time_hours"]), "value": str(row["value"])} for row in rows],
        period_hours=24.0,
        time_system=time_system,
    )


def _analyze_group(rows: list[dict[str, object]], rng: random.Random, n_permutations: int, n_bootstrap: int, time_system: str) -> dict[str, object]:
    units = {str(row.get("experimental_unit") or "").strip() for row in rows}
    unit = next(iter(units)) if len(units) == 1 else "mixed"
    base = {
        "n_observations": len(rows),
        "n_subjects": len({str(row["subject_id"]) for row in rows}),
        "n_biological_replicates": len({str(row["subject_id"]) for row in rows}),
        "n_unique_time_points": len({float(row["time_hours"]) for row in rows}),
        "experimental_unit": unit or "unspecified",
    }
    if unit == "mixed":
        base.update({"status": "blocked_mixed_experimental_units", "inference_warning": "A group contains more than one experimental_unit label; resolve metadata before inference."})
        return base
    if not unit or not _present(unit):
        base.update({"status": "blocked_experimental_unit_unspecified", "experimental_unit": "unspecified", "inference_warning": "No inference: explicitly declare experimental_unit or provide a metadata join; sample_id alone is not sufficient."})
        return base
    if unit.lower().replace(" ", "_") in {"technical_replicate", "technical_replicate_id"}:
        base.update({"status": "blocked_nonbiological_unit", "inference_warning": "Technical replicates cannot be treated as independent biological units; aggregate or model the biological replicate first."})
        return base
    if len(rows) < 4 or base["n_unique_time_points"] < 3:
        base.update({"status": "insufficient_or_invalid_time_series", "inference_warning": "No rhythm inference; at least four observations and three unique time points are required."})
        return base
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["subject_id"])] += 1
    repeated = sorted(subject for subject, count in counts.items() if count > 1)
    if repeated:
        base.update({"status": "blocked_repeated_subjects", "repeated_subject_ids": repeated, "inference_warning": "Inference is blocked because a biological replicate ID has repeated observations; use a pre-specified hierarchical/mixed model rather than treating rows as independent."})
        return base
    observed = _fit(rows, time_system)
    observed_amp = float(observed["amplitude"])
    null_amplitudes: list[float] = []
    original_times = [float(row["time_hours"]) for row in rows]
    for _ in range(n_permutations):
        shuffled = original_times[:]
        rng.shuffle(shuffled)
        permuted = [dict(row, time_hours=time) for row, time in zip(rows, shuffled)]
        null_amplitudes.append(float(_fit(permuted, time_system)["amplitude"]))
    p_value = (1.0 + sum(null >= observed_amp for null in null_amplitudes)) / (n_permutations + 1.0)
    bootstrap_amplitudes: list[float] = []
    bootstrap_phases: list[float] = []
    for _ in range(n_bootstrap):
        sample = [dict(rows[rng.randrange(len(rows))]) for _ in rows]
        if len({float(row["time_hours"]) for row in sample}) < 3:
            continue
        fit = _fit(sample, time_system)
        bootstrap_amplitudes.append(float(fit["amplitude"]))
        bootstrap_phases.append(float(fit["phase_peak_hours"]))
    warning = "Exploratory permutation/bootstrap only; confirm metadata, batch structure and a publication-grade mixed model before inferential claims."
    if unit.lower().replace(" ", "_") == "pooled_cell_sample":
        warning += " This is a pooled cell sample; the result is not an animal-level effect estimate."
    base.update({
        "status": "exploratory_inferential_cosinor",
        "period_hours": 24.0,
        "time_system": time_system,
        "observed_amplitude": observed_amp,
        "observed_phase_peak_hours": observed["phase_peak_hours"],
        "observed_r_squared": observed["r_squared"],
        "p_amplitude_permutation": p_value,
        "bootstrap_amplitude_ci95": [_percentile(bootstrap_amplitudes, 0.025), _percentile(bootstrap_amplitudes, 0.975)],
        "bootstrap_phase_ci95": [_percentile(bootstrap_phases, 0.025), _percentile(bootstrap_phases, 0.975)],
        "n_permutations": n_permutations,
        "n_bootstrap_success": len(bootstrap_amplitudes),
        "n_bootstrap_requested": n_bootstrap,
        "inference_warning": warning,
    })
    return base


def analyze_file(path: Path, n_permutations: int = 1000, n_bootstrap: int = 1000, seed: int = 20260906, metadata_path: Path | None = None, experimental_unit: str | None = None, time_system: str = "unknown") -> dict[str, object]:
    """Run exploratory inference only with an explicit and consistent time basis."""
    if n_permutations <= 0 or n_bootstrap <= 0:
        raise ValueError("n_permutations and n_bootstrap must be positive")
    normalized_time_system = _normalize_time_system(time_system)
    if not normalized_time_system:
        return {
            "status": "blocked_time_system_unspecified",
            "analysis_status": "not_executed",
            "scientific_status": "not_verified",
            "time_system": "unknown",
            "input_file": str(path),
            "metadata_source": str(metadata_path) if metadata_path else None,
            "issues": [{"type": "time_system_unspecified", "message": "Pass --time-system ZT or CT before inference."}],
            "inference_warning": "No fit was attempted because ZT/CT is part of the measurement definition, not an optional display label.",
        }
    input_metadata = _file_metadata(path)
    metadata_file_metadata = _file_metadata(metadata_path) if metadata_path else None
    groups, metadata_warnings, metadata_joined = _load_groups(path, metadata_path, experimental_unit, normalized_time_system)
    if metadata_joined and experimental_unit:
        observed_units = {str(row.get("experimental_unit") or "").strip() for rows in groups.values() for row in rows if _present(row.get("experimental_unit"))}
        declared_unit_clean = experimental_unit.strip()
        if _present(declared_unit_clean) and observed_units and observed_units != {declared_unit_clean}:
            raise ValueError(f"declared experimental_unit does not match metadata: {sorted(observed_units)}")
    results: list[dict[str, object]] = []
    inferential_indices: list[int] = []
    p_values: list[float] = []
    for index, key in enumerate(sorted(groups)):
        result = _analyze_group(groups[key], random.Random(seed + index), n_permutations, n_bootstrap, normalized_time_system)
        result.update({"gene_symbol": key[0], "cell_type": key[1], "background": key[2], "developmental_stage": key[3], "sex": key[4]})
        results.append(result)
        if result.get("status") == "exploratory_inferential_cosinor":
            inferential_indices.append(len(results) - 1)
            p_values.append(float(result["p_amplitude_permutation"]))
    q_values = _bh_adjust(p_values)
    for index, q_value in zip(inferential_indices, q_values):
        results[index]["q_amplitude_bh"] = q_value
    all_unspecified = bool(results) and all(result.get("status") == "blocked_experimental_unit_unspecified" for result in results)
    return {
        "status": "blocked_experimental_unit_unspecified" if all_unspecified else "exploratory_cosinor_inference",
        "analysis_status": "executed_exploratory",
        "scientific_status": "exploratory_not_verified",
        "formal_status": "blocked_requires_mixed_model",
        "time_system": normalized_time_system,
        "method": "fixed 24-hour cosinor + global time-label permutation + row bootstrap",
        "seed": seed,
        "n_permutations": n_permutations,
        "n_bootstrap": n_bootstrap,
        "input_file_metadata": input_metadata,
        "metadata_joined": metadata_joined,
        "metadata_source": str(metadata_path) if metadata_path else None,
        "metadata_file_metadata": metadata_file_metadata,
        "metadata_warnings": metadata_warnings,
        "multiple_testing_scope": "Benjamini-Hochberg across testable groups in this run",
        "n_groups": len(results),
        "groups": results,
        "inference_warning": "This output is exploratory and does not replace a biological-unit-aware mixed model or pre-registered analysis.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--experimental-unit")
    parser.add_argument("--time-system", choices=("ZT", "CT"), required=True, help="Circadian time basis for every labelled time token.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-permutations", type=int, default=1000)
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args(argv[1:])
    try:
        result = analyze_file(args.input, args.n_permutations, args.n_bootstrap, args.seed, args.metadata, args.experimental_unit, args.time_system)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return 0 if result["status"] == "exploratory_cosinor_inference" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
