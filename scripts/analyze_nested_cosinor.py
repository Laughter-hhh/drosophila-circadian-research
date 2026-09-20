#!/usr/bin/env python3
"""Exploratory 24-hour cosinor with biological-unit aggregation and cluster bootstrap.

This transparent bridge for nested data (multiple cells/ROIs per fly) requires
an explicit ZT or CT time basis. It aggregates subunits within biological
replicate × time, then resamples biological replicates rather than subunits.
It is not a substitute for a pre-specified mixed-effects model.
"""

from __future__ import annotations

import argparse
import csv
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
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NONE REPORTED", "."}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _normalize_time_system(value: str | None) -> str:
    normalized = (value or "").strip().upper()
    if normalized in {"", "UNKNOWN", "UNSPECIFIED"}:
        return ""
    if normalized not in {"ZT", "CT"}:
        raise ValueError("time_system must be ZT or CT")
    return normalized


def _parse_time(row: dict[str, str], expected_system: str = "ZT") -> float:
    if _present(row.get("time_hours")):
        value = float(row["time_hours"])
        if not math.isfinite(value):
            raise ValueError(f"time_hours must be finite: {row}")
        return value % 24.0
    token = (row.get("time") or row.get("ZT_or_CT") or "").strip()
    match = TIME_RE.search(token)
    if not match:
        raise ValueError(f"row needs numeric time_hours or ZT/CT token: {row}")
    basis = match.group(1).upper()
    expected = _normalize_time_system(expected_system)
    if expected and basis != expected:
        raise ValueError(f"time system mismatch: expected {expected}, observed {basis} in {token!r}")
    value = float(match.group(2))
    if not math.isfinite(value):
        raise ValueError(f"time token is nonfinite: {row}")
    return value % 24.0


def _fit(rows: list[dict[str, object]], time_system: str = "ZT") -> dict[str, object]:
    return analyze_rows(
        [{"subject_id": str(row["biological_replicate_id"]), "time_hours": str(row["time_hours"]), "value": str(row["value"])} for row in rows],
        period_hours=24.0,
        time_system=time_system,
    )


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


def _bh_adjust(p_values: list[float]) -> list[float]:
    if not p_values:
        return []
    order = sorted(range(len(p_values)), key=lambda index: p_values[index])
    adjusted = [1.0] * len(p_values)
    running = 1.0
    for rank, index in reversed(list(enumerate(order, start=1))):
        running = min(running, p_values[index] * len(p_values) / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


def _load_groups(path: Path, declared_unit: str | None = None, time_system: str = "ZT") -> dict[tuple[str, str, str], list[dict[str, object]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {"biological_replicate_id", "value"}
        if not required.issubset(fields) or not ({"time_hours", "time", "ZT_or_CT"} & fields):
            raise ValueError("input needs biological_replicate_id, value and time_hours/time/ZT_or_CT columns")
        groups: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
        for row_index, row in enumerate(reader):
            biological_id = (row.get("biological_replicate_id") or "").strip()
            if not biological_id:
                raise ValueError(f"biological_replicate_id is missing at row {row_index + 2}")
            try:
                time_hours = _parse_time(row, time_system)
                value = float(row["value"])
                if not math.isfinite(value):
                    raise ValueError("value must be finite")
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid nested-data row at {row_index + 2}: {row}") from exc
            unit = (row.get("experimental_unit") or "").strip() or (declared_unit or "").strip()
            subunit = (row.get("subunit_id") or row.get("cell_id") or row.get("roi_id") or f"row{row_index + 2}").strip()
            key = ((row.get("gene_symbol") or "").strip(), (row.get("cell_type") or "").strip(), (row.get("background") or "").strip())
            groups[key].append({"biological_replicate_id": biological_id, "time_hours": time_hours, "value": value, "subunit_id": subunit, "experimental_unit": unit})
    return dict(groups)


def _aggregate(rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]]]:
    grouped: dict[tuple[str, float], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["biological_replicate_id"]), float(row["time_hours"]))].append(row)
    aggregated: list[dict[str, object]] = []
    by_biological: dict[str, list[dict[str, object]]] = defaultdict(list)
    for (biological_id, time_hours), members in sorted(grouped.items()):
        mean_value = sum(float(member["value"]) for member in members) / len(members)
        aggregate = {"biological_replicate_id": biological_id, "time_hours": time_hours, "value": mean_value, "n_subunits": len(members)}
        aggregated.append(aggregate)
        by_biological[biological_id].append(aggregate)
    return aggregated, dict(by_biological)


def _analyze_group(rows: list[dict[str, object]], rng: random.Random, n_permutations: int, n_bootstrap: int, time_system: str = "ZT") -> dict[str, object]:
    units = {str(row.get("experimental_unit") or "").strip() for row in rows}
    unit = next(iter(units)) if len(units) == 1 else "mixed"
    base: dict[str, object] = {"n_raw_observations": len(rows), "experimental_unit": unit or "unspecified"}
    if unit == "mixed":
        base.update({"status": "blocked_mixed_experimental_units", "inference_warning": "Resolve experimental_unit labels before inference."})
        return base
    if not unit or unit.upper() in MISSING:
        base.update({"status": "blocked_experimental_unit_unspecified", "inference_warning": "No inference: declare experimental_unit explicitly; nested row IDs do not establish independence."})
        return base
    if unit.lower().replace(" ", "_") in {"technical_replicate", "technical_replicate_id"}:
        base.update({"status": "blocked_nonbiological_unit", "inference_warning": "Technical replicates cannot be independent biological units."})
        return base

    aggregated, by_biological = _aggregate(rows)
    biological_ids = sorted(by_biological)
    unique_times = sorted({float(row["time_hours"]) for row in aggregated})
    subunit_counts = [int(row["n_subunits"]) for row in aggregated]
    base.update({
        "n_aggregated_biological_unit_time_means": len(aggregated),
        "n_biological_replicates": len(biological_ids),
        "n_unique_time_points": len(unique_times),
        "mean_subunits_per_biological_unit_time": sum(subunit_counts) / len(subunit_counts) if subunit_counts else None,
        "max_subunits_per_biological_unit_time": max(subunit_counts) if subunit_counts else 0,
    })
    if len(biological_ids) < 4 or len(aggregated) < 4 or len(unique_times) < 3:
        base.update({"status": "insufficient_or_invalid_nested_time_series", "inference_warning": "Need at least four biological replicates, four aggregated observations and three unique time points for this exploratory model."})
        return base

    observed = _fit(aggregated, time_system)
    observed_amp = float(observed["amplitude"])
    within_repeated = sum(len(values) >= 2 for values in by_biological.values())
    permutation_mode = "within_biological_unit_time_shuffle" if within_repeated else "global_time_label_shuffle"
    null_amplitudes: list[float] = []
    if within_repeated:
        for _ in range(n_permutations):
            permuted: list[dict[str, object]] = []
            for biological_id in biological_ids:
                cluster_rows = by_biological[biological_id]
                times = [float(row["time_hours"]) for row in cluster_rows]
                shuffled = times[:]
                rng.shuffle(shuffled)
                for row, time_hours in zip(cluster_rows, shuffled):
                    permuted.append(dict(row, time_hours=time_hours))
            null_amplitudes.append(float(_fit(permuted, time_system)["amplitude"]))
    else:
        original_times = [float(row["time_hours"]) for row in aggregated]
        for _ in range(n_permutations):
            shuffled = original_times[:]
            rng.shuffle(shuffled)
            permuted = [dict(row, time_hours=time_hours) for row, time_hours in zip(aggregated, shuffled)]
            null_amplitudes.append(float(_fit(permuted, time_system)["amplitude"]))
    p_value = (1.0 + sum(null >= observed_amp for null in null_amplitudes)) / (n_permutations + 1.0)

    bootstrap_amplitudes: list[float] = []
    bootstrap_phases: list[float] = []
    for _ in range(n_bootstrap):
        sampled_ids = [biological_ids[rng.randrange(len(biological_ids))] for _ in biological_ids]
        sampled: list[dict[str, object]] = []
        for draw_index, biological_id in enumerate(sampled_ids):
            for row in by_biological[biological_id]:
                sampled.append(dict(row, biological_replicate_id=f"{biological_id}__bootstrap{draw_index}"))
        if len({float(row["time_hours"]) for row in sampled}) < 3:
            continue
        fit = _fit(sampled, time_system)
        bootstrap_amplitudes.append(float(fit["amplitude"]))
        bootstrap_phases.append(float(fit["phase_peak_hours"]))
    warning = "Biological-unit aggregation plus cluster bootstrap is exploratory; confirm with a pre-specified mixed-effects model before publication claims."
    if not within_repeated:
        warning += " Each biological replicate contributes one time point; permutation used global time-label shuffling."
    if max(subunit_counts) <= 1:
        warning += " No within-unit subunit replication was detected in the input."
    base.update({
        "status": "exploratory_nested_cosinor", "period_hours": 24.0, "time_system": time_system,
        "observed_amplitude": observed_amp, "observed_phase_peak_hours": observed["phase_peak_hours"], "observed_r_squared": observed["r_squared"],
        "p_amplitude_permutation": p_value,
        "bootstrap_amplitude_ci95": [_percentile(bootstrap_amplitudes, 0.025), _percentile(bootstrap_amplitudes, 0.975)],
        "bootstrap_phase_ci95": [_percentile(bootstrap_phases, 0.025), _percentile(bootstrap_phases, 0.975)],
        "n_permutations": n_permutations, "n_bootstrap_success": len(bootstrap_amplitudes), "n_bootstrap_requested": n_bootstrap,
        "permutation_mode": permutation_mode, "inference_warning": warning,
    })
    return base


def analyze_file(path: Path, n_permutations: int = 1000, n_bootstrap: int = 1000, seed: int = 20260906, experimental_unit: str | None = None, time_system: str = "unknown") -> dict[str, object]:
    if n_permutations <= 0 or n_bootstrap <= 0:
        raise ValueError("n_permutations and n_bootstrap must be positive")
    normalized_time_system = _normalize_time_system(time_system)
    if not normalized_time_system:
        return {"status": "blocked_time_system_unspecified", "analysis_status": "not_executed", "scientific_status": "not_verified", "time_system": "unknown", "input_file": str(path), "issues": [{"type": "time_system_unspecified", "message": "Pass --time-system ZT or CT before inference."}], "inference_warning": "No fit was attempted because ZT/CT is part of the measurement definition, not an optional display label."}
    groups = _load_groups(path, experimental_unit, normalized_time_system)
    results: list[dict[str, object]] = []
    inferential_indices: list[int] = []
    p_values: list[float] = []
    for index, key in enumerate(sorted(groups)):
        result = _analyze_group(groups[key], random.Random(seed + index), n_permutations, n_bootstrap, normalized_time_system)
        result.update({"gene_symbol": key[0], "cell_type": key[1], "background": key[2]})
        results.append(result)
        if result.get("status") == "exploratory_nested_cosinor":
            inferential_indices.append(len(results) - 1)
            p_values.append(float(result["p_amplitude_permutation"]))
    q_values = _bh_adjust(p_values)
    for index, q_value in zip(inferential_indices, q_values):
        results[index]["q_amplitude_bh"] = q_value
    all_blocked = bool(results) and all(result["status"] == "blocked_experimental_unit_unspecified" for result in results)
    return {
        "status": "blocked_experimental_unit_unspecified" if all_blocked else "exploratory_nested_cosinor_inference",
        "analysis_status": "executed_exploratory", "scientific_status": "exploratory_not_verified", "formal_status": "blocked_requires_mixed_model",
        "time_system": normalized_time_system,
        "method": "fixed 24-hour cosinor on biological-unit × time means + cluster bootstrap", "seed": seed, "n_permutations": n_permutations, "n_bootstrap": n_bootstrap,
        "n_groups": len(results), "groups": results,
        "inference_warning": "Exploratory nested analysis only; a publication-grade mixed-effects model remains required.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--experimental-unit")
    parser.add_argument("--time-system", choices=("ZT", "CT"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--n-permutations", type=int, default=1000)
    parser.add_argument("--n-bootstrap", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260906)
    args = parser.parse_args(argv[1:])
    try:
        result = analyze_file(args.input, args.n_permutations, args.n_bootstrap, args.seed, args.experimental_unit, args.time_system)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
