#!/usr/bin/env python3
"""Validate per-panel provenance fields in a Markdown reading report.

Structural validation cannot prove links resolve, claims are accurate, or images
were actually opened and inspected.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED_COLUMNS = (
    "panel_id",
    "image_status",
    "caption_status",
    "source/version/page/direct link",
    "caption-supported labels, groups and readout",
    "visual-only unknown/unavailable",
    "n and experimental unit (or unknown)",
    "interpretation/caveat",
)
IMAGE_STATUSES = {"inspected", "linked_not_inspected", "unavailable"}
CAPTION_STATUSES = {"available", "partial", "unavailable"}
URL_OR_DOI = re.compile(r"https?://\S+|\bdoi\s*:?\s*10\.\d{4,9}/\S+", re.IGNORECASE)
STATUS_TOKEN = re.compile(r"^[a-z_]+", re.IGNORECASE)


def _cells(line: str) -> list[str] | None:
    """Split a pipe table row while preserving escaped pipes in cell text."""
    value = line.strip()
    if not value.startswith("|"):
        return None
    value = value[1:]
    if value.endswith("|") and not value.endswith("\\|"):
        value = value[:-1]
    cells: list[str] = []
    cell: list[str] = []
    i = 0
    while i < len(value):
        if value[i] == "\\" and i + 1 < len(value) and value[i + 1] == "|":
            cell.append("|")
            i += 2
        elif value[i] == "|":
            cells.append("".join(cell).strip())
            cell = []
            i += 1
        else:
            cell.append(value[i])
            i += 1
    cells.append("".join(cell).strip())
    return cells


def _separator(cells: list[str]) -> bool:
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def validate(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    issues: list[dict[str, object]] = []
    panel_ids: set[str] = set()
    tables = rows = 0
    i = 0
    while i + 1 < len(lines):
        header, rule = _cells(lines[i]), _cells(lines[i + 1])
        if header is None or rule is None or not _separator(rule):
            i += 1
            continue
        names = [re.sub(r"\s+", " ", cell.strip().lower()) for cell in header]
        if not ({"panel_id", "image_status", "caption_status"} & set(names)):
            i += 1
            continue

        tables += 1
        missing = [name for name in REQUIRED_COLUMNS if name not in names]
        if missing:
            issues.append({"line": i + 1, "table": tables, "type": "missing_required_columns", "columns": missing})
            i += 2
            while i < len(lines) and _cells(lines[i]) is not None:
                i += 1
            continue
        positions = {name: names.index(name) for name in REQUIRED_COLUMNS}
        i += 2
        while i < len(lines):
            cells = _cells(lines[i])
            if cells is None:
                break
            line_no = i + 1
            i += 1
            if _separator(cells):
                continue
            rows += 1
            if len(cells) != len(header):
                issues.append({"line": line_no, "table": tables, "type": "wrong_column_count", "expected": len(header), "observed": len(cells)})
                continue

            data = {name: cells[pos] for name, pos in positions.items()}
            panel_id = data["panel_id"].strip()
            key = panel_id.casefold()
            if not panel_id:
                issues.append({"line": line_no, "type": "missing_panel_id"})
            elif key in panel_ids:
                issues.append({"line": line_no, "panel_id": panel_id, "type": "duplicate_panel_id"})
            panel_ids.add(key)

            image = STATUS_TOKEN.match(data["image_status"].strip())
            image_value = image.group(0).lower() if image else ""
            if image_value not in IMAGE_STATUSES:
                issues.append({"line": line_no, "panel_id": panel_id, "type": "invalid_image_status", "value": data["image_status"]})
            caption = STATUS_TOKEN.match(data["caption_status"].strip())
            caption_value = caption.group(0).lower() if caption else ""
            if caption_value not in CAPTION_STATUSES:
                issues.append({"line": line_no, "panel_id": panel_id, "type": "invalid_caption_status", "value": data["caption_status"]})
            if not URL_OR_DOI.search(data["source/version/page/direct link"]):
                issues.append({"line": line_no, "panel_id": panel_id, "type": "missing_direct_source_link"})
            for name in REQUIRED_COLUMNS[4:]:
                if not data[name].strip():
                    issues.append({"line": line_no, "panel_id": panel_id, "type": "missing_required_content", "column": name})

    if not tables:
        issues.append({"type": "no_panel_inventory_table"})
    elif not rows:
        issues.append({"type": "empty_panel_inventory"})
    return {
        "status": "verified_literature_panel_inventory" if rows and not issues else "invalid_literature_panel_inventory",
        "n_tables": tables,
        "n_rows": rows,
        "n_unique_panel_ids": len(panel_ids),
        "issues": issues,
        "scope_warning": "Structural validation only; source accessibility, claim support, biological accuracy, and actual visual inspection require manual review.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Markdown report containing panel inventory tables")
    parser.add_argument("--output", type=Path, help="optional JSON result path")
    args = parser.parse_args(argv[1:])
    try:
        result = validate(args.input)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0 if result["status"] == "verified_literature_panel_inventory" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
