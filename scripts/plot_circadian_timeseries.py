#!/usr/bin/env python3
"""Create a dependency-free, auditable SVG plot from circadian measurements.

This is a visualization step, not a rhythm test. It preserves individual
rows as points and overlays deterministic time-point means by an optional
group column. It requires an explicit ZT/CT declaration and refuses to pool
multiple readouts, physical units, or missing biological group labels silently.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_AVAILABLE", "NOT_APPLICABLE", "NOT_REPORTED", "."}
COLORS = ("#1b6ca8", "#d1495b", "#2a9d8f", "#e9c46a", "#7b2cbf", "#f77f00")


def _present(value: object) -> bool:
    return str(value or "").strip().upper() not in MISSING


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: object, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric: {value!r}") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite: {value!r}")
    return number


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values)


def _scale(value: float, lower: float, upper: float, pixel_lower: float, pixel_upper: float) -> float:
    if upper == lower:
        return (pixel_lower + pixel_upper) / 2.0
    return pixel_lower + (value - lower) * (pixel_upper - pixel_lower) / (upper - lower)


def _svg_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _validate_labels(rows: list[dict[str, str]], metric_name: str | None) -> tuple[list[dict[str, str]], str, str]:
    observed_metrics = sorted({(row.get("metric_name") or "").strip() for row in rows if _present(row.get("metric_name"))})
    missing_metrics = sum(not _present(row.get("metric_name")) for row in rows)
    selected_metric = (metric_name or "").strip()
    if selected_metric:
        if missing_metrics:
            raise ValueError("metric_name is missing from some rows; cannot select a metric safely")
        if selected_metric not in observed_metrics:
            raise ValueError(f"requested metric_name not found: {selected_metric}")
    elif len(observed_metrics) > 1 or (observed_metrics and missing_metrics):
        raise ValueError("multiple or incompletely labelled metric_name values require --metric-name or separate input")
    else:
        selected_metric = observed_metrics[0] if observed_metrics else "unspecified"
    selected_rows = [row for row in rows if (row.get("metric_name") or "").strip() == selected_metric or (selected_metric == "unspecified" and not _present(row.get("metric_name")))]
    observed_units = sorted({(row.get("value_unit") or "").strip() for row in selected_rows if _present(row.get("value_unit"))})
    missing_units = sum(not _present(row.get("value_unit")) for row in selected_rows)
    if len(observed_units) > 1 or (observed_units and missing_units):
        raise ValueError("multiple or incompletely labelled value_unit values cannot be plotted together")
    value_unit = observed_units[0] if observed_units else "unspecified"
    return selected_rows, selected_metric, value_unit


def plot(
    input_path: Path,
    output_svg: Path,
    report_path: Path,
    *,
    time_system: str,
    time_column: str = "time_hours",
    value_column: str = "value",
    group_column: str | None = "biological_replicate_id",
    metric_name: str | None = None,
    title: str = "Circadian time series",
    width: int = 900,
    height: int = 560,
) -> dict[str, object]:
    normalized_system = (time_system or "").strip().upper()
    if normalized_system not in {"ZT", "CT"}:
        raise ValueError("time_system must be ZT or CT")
    if width < 400 or height < 300:
        raise ValueError("width must be at least 400 and height at least 300")
    with input_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        required = {time_column, value_column}
        missing = sorted(required - fields)
        if missing:
            raise ValueError(f"input is missing columns: {', '.join(missing)}")
        if group_column and group_column not in fields:
            raise ValueError(f"group column {group_column!r} is missing; pass --group-column '' to explicitly pool rows")
        rows = list(reader)
    selected_rows, selected_metric, value_unit = _validate_labels(rows, metric_name)
    if group_column and any(not _present(row.get(group_column)) for row in selected_rows):
        raise ValueError(f"group column {group_column!r} is missing or incomplete; refusing silent pooling")
    parsed: list[dict[str, object]] = []
    for row in selected_rows:
        parsed.append({
            "time": _number(row.get(time_column), time_column),
            "value": _number(row.get(value_column), value_column),
            "group": (row.get(group_column) or "all").strip() if group_column else "all",
        })
    if len(parsed) < 1:
        raise ValueError("no rows remain after metric selection")
    x_values = [float(row["time"]) for row in parsed]
    y_values = [float(row["value"]) for row in parsed]
    x_min, x_max = min(x_values), max(x_values)
    y_min, y_max = min(y_values), max(y_values)
    x_pad = max((x_max - x_min) * 0.05, 1.0)
    y_pad = max((y_max - y_min) * 0.08, 0.1)
    x_lower, x_upper = x_min - x_pad, x_max + x_pad
    y_lower, y_upper = y_min - y_pad, y_max + y_pad
    left, right, top, bottom = 82.0, float(width - 36), 76.0, float(height - 68)
    grouped: dict[str, dict[float, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in parsed:
        grouped[str(row["group"])][float(row["time"])].append(float(row["value"]))
    group_names = sorted(grouped)
    svg: list[str] = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    svg.append('<rect width="100%" height="100%" fill="white"/>')
    svg.append(f'<text x="{width / 2:g}" y="30" text-anchor="middle" font-family="Arial" font-size="18" font-weight="bold">{_svg_escape(title)}</text>')
    svg.append(f'<text x="{width / 2:g}" y="52" text-anchor="middle" font-family="Arial" font-size="12">{_svg_escape(normalized_system)} · {_svg_escape(selected_metric)} [{_svg_escape(value_unit)}]</text>')
    svg.append(f'<line x1="{left:g}" y1="{bottom:g}" x2="{right:g}" y2="{bottom:g}" stroke="#222"/>')
    svg.append(f'<line x1="{left:g}" y1="{top:g}" x2="{left:g}" y2="{bottom:g}" stroke="#222"/>')
    for tick in range(5):
        x = x_lower + (x_upper - x_lower) * tick / 4.0
        px = _scale(x, x_lower, x_upper, left, right)
        svg.append(f'<line x1="{px:g}" y1="{bottom:g}" x2="{px:g}" y2="{bottom + 5:g}" stroke="#222"/>')
        svg.append(f'<text x="{px:g}" y="{bottom + 22:g}" text-anchor="middle" font-family="Arial" font-size="11">{x:g}</text>')
    for tick in range(5):
        y = y_lower + (y_upper - y_lower) * tick / 4.0
        py = _scale(y, y_lower, y_upper, bottom, top)
        svg.append(f'<line x1="{left - 5:g}" y1="{py:g}" x2="{left:g}" y2="{py:g}" stroke="#222"/>')
        svg.append(f'<text x="{left - 10:g}" y="{py + 4:g}" text-anchor="end" font-family="Arial" font-size="11">{y:.3g}</text>')
    svg.append(f'<text x="{(left + right) / 2:g}" y="{height - 18:g}" text-anchor="middle" font-family="Arial" font-size="12">time ({normalized_system})</text>')
    svg.append(f'<text x="18" y="{(top + bottom) / 2:g}" transform="rotate(-90 18 {(top + bottom) / 2:g})" text-anchor="middle" font-family="Arial" font-size="12">value ({_svg_escape(value_unit)})</text>')
    for row in parsed:
        color = COLORS[group_names.index(str(row["group"])) % len(COLORS)]
        px = _scale(float(row["time"]), x_lower, x_upper, left, right)
        py = _scale(float(row["value"]), y_lower, y_upper, bottom, top)
        svg.append(f'<circle cx="{px:g}" cy="{py:g}" r="3.2" fill="{color}" fill-opacity="0.48"><title>{_svg_escape(row["group"])}: {_svg_escape(row["time"])} = {_svg_escape(row["value"])}</title></circle>')
    for index, group in enumerate(group_names):
        color = COLORS[index % len(COLORS)]
        means = sorted((time, _mean(values)) for time, values in grouped[group].items())
        points = " ".join(f"{_scale(time, x_lower, x_upper, left, right):g},{_scale(value, y_lower, y_upper, bottom, top):g}" for time, value in means)
        if len(means) >= 2:
            svg.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        legend_x = right - 160
        legend_y = top + 16 * index
        svg.append(f'<line x1="{legend_x:g}" y1="{legend_y:g}" x2="{legend_x + 18:g}" y2="{legend_y:g}" stroke="{color}" stroke-width="3"/>')
        svg.append(f'<text x="{legend_x + 24:g}" y="{legend_y + 4:g}" font-family="Arial" font-size="11">{_svg_escape(group)}</text>')
    svg.append('</svg>')
    svg_text = "\n".join(svg) + "\n"
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    output_svg.write_text(svg_text, encoding="utf-8")
    report = {
        "status": "verified_visualization_export",
        "analysis_status": "executed_visualization_only",
        "scientific_status": "not_a_rhythm_test",
        "time_system": normalized_system,
        "metric_name": selected_metric,
        "value_unit": value_unit,
        "group_column": group_column,
        "n_rows": len(parsed),
        "n_groups": len(group_names),
        "groups": group_names,
        "input_file_metadata": {"path": str(input_path), "sha256": _sha256(input_path), "size_bytes": input_path.stat().st_size},
        "output_file_metadata": {"path": str(output_svg), "sha256": _sha256(output_svg), "size_bytes": output_svg.stat().st_size},
        "inference_warning": "SVG export preserves raw rows and deterministic time-point means; it does not estimate rhythmicity, significance or causality.",
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output-svg", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--time-system", choices=("ZT", "CT"), required=True)
    parser.add_argument("--time-column", default="time_hours")
    parser.add_argument("--value-column", default="value")
    parser.add_argument("--group-column", default="biological_replicate_id")
    parser.add_argument("--metric-name")
    parser.add_argument("--title", default="Circadian time series")
    parser.add_argument("--width", type=int, default=900)
    parser.add_argument("--height", type=int, default=560)
    args = parser.parse_args(argv[1:])
    try:
        plot(args.input, args.output_svg, args.report, time_system=args.time_system, time_column=args.time_column, value_column=args.value_column, group_column=args.group_column, metric_name=args.metric_name, title=args.title, width=args.width, height=args.height)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
