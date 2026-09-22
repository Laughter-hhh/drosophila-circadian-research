#!/usr/bin/env python3
"""Audit whether requested design factors are independently observed in a CSV."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


BLANK = "<blank>"


def _display_path(path: Path) -> str:
    """Return a stable path label rather than embedding a machine-specific absolute path."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def _value(row: dict[str, str], field: str) -> str:
    value = (row.get(field) or "").strip()
    return value if value else BLANK


def _pair_report(rows: list[dict[str, str]], factor_a: str, factor_b: str) -> dict[str, object]:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[_value(row, factor_a)][_value(row, factor_b)] += 1

    a_to_b = {level: sorted(counts) for level, counts in sorted(table.items())}
    reverse: dict[str, set[str]] = defaultdict(set)
    for level_a, levels_b in a_to_b.items():
        for level_b in levels_b:
            reverse[level_b].add(level_a)
    b_to_a = {level: sorted(levels) for level, levels in sorted(reverse.items())}
    observed_pairs = [
        (level_a, level_b)
        for level_a, counts in sorted(table.items())
        for level_b in sorted(counts)
    ]
    has_blank = any(BLANK in pair for pair in observed_pairs)
    perfectly_confounded = (
        len(observed_pairs) > 1
        and not has_blank
        and all(len(levels) == 1 for levels in a_to_b.values())
        and all(len(levels) == 1 for levels in b_to_a.values())
    )
    status = "warning" if perfectly_confounded or has_blank else "ok"
    warnings = []
    if perfectly_confounded:
        warnings.append(
            f"{factor_a} and {factor_b} are perfectly confounded in observed rows; "
            "their independent effects are not estimable from this table"
        )
    if has_blank:
        warnings.append("blank values occur in at least one factor; do not treat them as a known level")
    return {
        "factor_a": factor_a,
        "factor_b": factor_b,
        "n_rows": len(rows),
        "cross_tab": {
            level_a: {level_b: table[level_a][level_b] for level_b in sorted(table[level_a])}
            for level_a in sorted(table)
        },
        "factor_a_to_b_levels": a_to_b,
        "factor_b_to_a_levels": b_to_a,
        "perfectly_confounded": perfectly_confounded,
        "status": status,
        "warnings": warnings,
    }


def inspect(path: Path, factors: list[str]) -> dict[str, object]:
    factors = [factor.strip() for factor in factors]
    if len(factors) < 2 or len(set(factors)) != len(factors) or any(not factor for factor in factors):
        raise ValueError("provide at least two distinct non-blank --factor values")
    if not path.is_file():
        raise ValueError(f"input CSV does not exist: {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV has no header")
        missing = sorted(set(factors).difference(reader.fieldnames))
        if missing:
            raise ValueError("missing requested factor column(s): " + ", ".join(missing))
        rows = list(reader)
    if not rows:
        raise ValueError("CSV contains no data rows")

    missing_counts = {
        factor: sum(_value(row, factor) == BLANK for row in rows)
        for factor in factors
    }
    level_counts = {
        factor: dict(sorted(Counter(_value(row, factor) for row in rows).items()))
        for factor in factors
    }
    pairs = [_pair_report(rows, a, b) for a, b in itertools.combinations(factors, 2)]
    warnings = [
        f"{factor} contains {count} blank value(s)"
        for factor, count in missing_counts.items()
        if count
    ]
    for pair in pairs:
        warnings.extend(pair["warnings"])
    return {
        "status": "warning" if warnings else "ok",
        "input": _display_path(path),
        "n_rows": len(rows),
        "factors": factors,
        "level_counts": level_counts,
        "missing_counts": missing_counts,
        "pair_reports": pairs,
        "warnings": warnings,
        "interpretation": (
            "A perfectly confounded pair has a one-to-one mapping of observed levels; "
            "the table cannot separate the two factor effects without additional design strata."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--factor", action="append", required=True, help="factor column to audit; repeat for each factor")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:] if argv is not None else None)
    try:
        result = inspect(args.input, args.factor)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
