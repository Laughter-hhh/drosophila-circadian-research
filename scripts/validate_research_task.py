#!/usr/bin/env python3
"""Validate the JSON research-task contract used by this skill."""

from __future__ import annotations

import json
import sys
from pathlib import Path


REQUIRED = (
    "task_id",
    "status",
    "research_question",
    "species",
    "experimental_unit",
    "primary_readout",
    "required_metadata",
    "expected_outputs",
    "acceptance_tests",
)
STATUSES = {"planning", "executed", "verified", "blocked"}


def validate(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"file not found: {path}"]
    except json.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["contract must be a JSON object"]
    for key in REQUIRED:
        if key not in data:
            errors.append(f"missing required field: {key}")
    if data.get("status") not in STATUSES:
        errors.append(f"status must be one of: {', '.join(sorted(STATUSES))}")
    for key in ("required_metadata", "expected_outputs", "acceptance_tests", "alternative_hypotheses"):
        if key in data and not isinstance(data[key], list):
            errors.append(f"{key} must be a list")
    if data.get("status") in {"executed", "verified"}:
        for key in ("input_files", "analysis_plan"):
            if not data.get(key):
                errors.append(f"{key} is required for status={data['status']}")
    return errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: validate_research_task.py TASK.json", file=sys.stderr)
        return 2
    errors = validate(Path(argv[1]))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("OK: research task contract is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
