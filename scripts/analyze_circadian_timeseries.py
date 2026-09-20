#!/usr/bin/env python3
"""Exploratory fixed-period cosinor analysis for a CSV time series.

Required columns: subject_id,time_hours,value. This is descriptive only; it
does not perform a biological-unit-aware significance test. ZT/CT is required
because the time basis is part of the measurement definition.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Iterable, Mapping


def _normalize_time_system(value: str | None) -> str:
    normalized = str(value or "").strip().upper()
    if normalized not in {"ZT", "CT"}:
        raise ValueError("time_system must be ZT or CT")
    return normalized


def _solve_linear(matrix: list[list[float]], vector: list[float]) -> list[float]:
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    size = len(vector)
    for pivot in range(size):
        best = max(range(pivot, size), key=lambda idx: abs(augmented[idx][pivot]))
        if abs(augmented[best][pivot]) < 1e-12:
            raise ValueError("design matrix is singular; use more than one unique time")
        augmented[pivot], augmented[best] = augmented[best], augmented[pivot]
        divisor = augmented[pivot][pivot]
        augmented[pivot] = [value / divisor for value in augmented[pivot]]
        for row in range(size):
            if row == pivot:
                continue
            factor = augmented[row][pivot]
            augmented[row] = [a - factor * b for a, b in zip(augmented[row], augmented[pivot])]
    return [augmented[idx][-1] for idx in range(size)]


def analyze_rows(rows: Iterable[Mapping[str, str]], period_hours: float = 24.0, time_system: str = "unknown") -> dict[str, object]:
    normalized_time_system = _normalize_time_system(time_system)
    if not math.isfinite(period_hours) or period_hours <= 0:
        raise ValueError("period_hours must be a positive finite number")
    parsed: list[tuple[str, float, float]] = []
    for row in rows:
        try:
            subject = str(row["subject_id"])
            time = float(row["time_hours"])
            value = float(row["value"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"each row needs numeric subject_id, time_hours and value: {row}") from exc
        if not math.isfinite(time) or not math.isfinite(value):
            raise ValueError(f"subject_id, time_hours and value must be finite: {row}")
        parsed.append((subject, time, value))
    if len(parsed) < 4 or len({time for _, time, _ in parsed}) < 3:
        raise ValueError("need at least four observations and three unique time points")

    design: list[list[float]] = []
    values: list[float] = []
    for _, time, value in parsed:
        theta = 2.0 * math.pi * time / period_hours
        design.append([1.0, math.cos(theta), math.sin(theta)])
        values.append(value)

    xtx = [[sum(row[i] * row[j] for row in design) for j in range(3)] for i in range(3)]
    xty = [sum(row[i] * value for row, value in zip(design, values)) for i in range(3)]
    beta0, beta_cos, beta_sin = _solve_linear(xtx, xty)
    fitted = [beta0 + beta_cos * row[1] + beta_sin * row[2] for row in design]
    mean_value = sum(values) / len(values)
    sse = sum((value - fit) ** 2 for value, fit in zip(values, fitted))
    sst = sum((value - mean_value) ** 2 for value in values)
    r_squared = None if sst == 0 else 1.0 - sse / sst
    amplitude = math.hypot(beta_cos, beta_sin)
    phase_hours = (math.atan2(beta_sin, beta_cos) * period_hours / (2.0 * math.pi)) % period_hours
    if math.isclose(phase_hours, period_hours, rel_tol=0.0, abs_tol=1e-9):
        phase_hours = 0.0
    result = {
        "status": "exploratory_fixed_period_cosinor", "time_system": normalized_time_system, "period_hours": period_hours,
        "mesor": beta0, "amplitude": amplitude, "phase_peak_hours": phase_hours, "r_squared": r_squared,
        "n_observations": len(parsed), "n_subjects": len({subject for subject, _, _ in parsed}), "n_unique_time_points": len({time for _, time, _ in parsed}),
        "inference_warning": "Descriptive fit only; use a biological-unit-aware model or permutation test for inference.",
    }
    if not all(math.isfinite(float(result[key])) for key in ("mesor", "amplitude", "phase_peak_hours")):
        raise ValueError("fit produced a non-finite result")
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--period-hours", type=float, default=24.0)
    parser.add_argument("--time-system", choices=("ZT", "CT"), required=True)
    args = parser.parse_args(argv[1:])
    try:
        with args.input.open(newline="", encoding="utf-8") as handle:
            result = analyze_rows(csv.DictReader(handle), args.period_hours, args.time_system)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
