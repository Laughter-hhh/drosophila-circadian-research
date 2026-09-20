#!/usr/bin/env python3
"""Validate a portable, replayable ephys trace-analysis manifest."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.validate_public_dataset_manifest import _is_safe_relative, _norm_rel, _resolve, _sha256
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_public_dataset_manifest import _is_safe_relative, _norm_rel, _resolve, _sha256

REQUIRED = {"manifest_id", "analysis_scope", "analysis_context", "files", "runs"}
ROLES = {"raw", "trace_export", "metadata", "raw_qc", "derived", "report"}
RUN_STATUSES = {"executed", "verified"}
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_SCRIPTS = {
    "scripts/validate_experiment_metadata.py",
    "scripts/validate_raw_qc_provenance.py",
    "scripts/derive_trace_measurements.py",
    "scripts/validate_preanalysis_bundle.py",
    "scripts/analyze_preanalysis_cosinor.py",
}


def _safe_record_path(value: Any) -> str:
    return _norm_rel(value)


def _path_issue(value: str) -> bool:
    return not _is_safe_relative(value) or "\x00" in value


def _read_raw_qc(path: Path, root: Path, files: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for line, row in enumerate(rows, start=2):
        if (row.get("file_status") or "").strip().lower() != "present":
            continue
        raw_rel = _safe_record_path(row.get("raw_file_path"))
        if _path_issue(raw_rel):
            issues.append({"line": line, "type": "raw_file_path_must_be_safe_relative", "path": raw_rel})
            continue
        raw_resolved = (path.parent / Path(raw_rel)).resolve()
        try:
            raw_repo_rel = raw_resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            issues.append({"line": line, "type": "raw_file_resolves_outside_root", "path": raw_rel})
            continue
        record = files.get(raw_repo_rel)
        if record is None:
            issues.append({"line": line, "type": "raw_file_not_registered", "path": raw_repo_rel})
            continue
        digest = (row.get("raw_file_sha256") or "").strip().lower()
        if digest != str(record.get("sha256") or "").lower():
            issues.append({"line": line, "type": "raw_qc_hash_disagrees_with_manifest", "path": raw_repo_rel})
    return issues


def validate_payload(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if not isinstance(payload, dict):
        return {"status": "invalid_ephys_trace_replay_manifest", "issues": [{"type": "top_level_must_be_object"}]}
    missing = sorted(REQUIRED - set(payload))
    if missing:
        return {"status": "invalid_ephys_trace_replay_manifest", "issues": [{"type": "missing_fields", "fields": missing}]}
    context = payload.get("analysis_context")
    if not isinstance(context, dict):
        issues.append({"type": "analysis_context_must_be_object"})
    else:
        for field in ("species", "assay", "experimental_unit", "time_system", "scientific_status"):
            if not str(context.get(field) or "").strip():
                issues.append({"type": "analysis_context_missing_field", "field": field})
        if str(context.get("assay") or "").strip().lower() != "ephys":
            issues.append({"type": "analysis_context_assay_must_be_ephys"})
    files_raw = payload.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        issues.append({"type": "files_must_be_nonempty_list"})
        files_raw = []
    files: dict[str, dict[str, Any]] = {}
    file_checks: list[dict[str, Any]] = []
    for index, record in enumerate(files_raw, start=1):
        if not isinstance(record, dict):
            issues.append({"index": index, "type": "file_record_must_be_object"})
            continue
        relative = _safe_record_path(record.get("path"))
        role = str(record.get("role") or "").strip().lower()
        expected = str(record.get("sha256") or "").strip().lower()
        if _path_issue(relative):
            issues.append({"index": index, "type": "file_path_must_be_safe_relative", "path": relative})
            continue
        if role not in ROLES:
            issues.append({"index": index, "type": "invalid_file_role", "role": role})
        if not SHA_RE.fullmatch(expected):
            issues.append({"index": index, "type": "invalid_file_sha256", "path": relative})
        if relative in files:
            issues.append({"index": index, "type": "duplicate_file_path", "path": relative})
        files[relative] = record
        resolved = _resolve(root, relative)
        check: dict[str, Any] = {"path": relative, "expected_sha256": expected}
        if not resolved.is_file():
            issues.append({"index": index, "type": "file_not_found", "path": relative})
            check["status"] = "missing"
        else:
            observed = _sha256(resolved)
            check["observed_sha256"] = observed
            check["status"] = "hash_verified" if observed == expected else "hash_mismatch"
            if observed != expected:
                issues.append({"index": index, "type": "file_hash_mismatch", "path": relative})
        file_checks.append(check)
    raw_qc_records = [path for path, record in files.items() if str(record.get("role") or "").lower() == "raw_qc"]
    if len(raw_qc_records) != 1:
        issues.append({"type": "requires_exactly_one_raw_qc_file", "n_raw_qc_files": len(raw_qc_records)})
    elif _resolve(root, raw_qc_records[0]).is_file():
        issues.extend(_read_raw_qc(_resolve(root, raw_qc_records[0]), root, files))

    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        issues.append({"type": "runs_must_be_nonempty_list"})
        runs = []
    run_checks: list[dict[str, Any]] = []
    for index, run in enumerate(runs, start=1):
        if not isinstance(run, dict):
            issues.append({"index": index, "type": "run_record_must_be_object"})
            continue
        run_id = str(run.get("run_id") or "").strip()
        script = _safe_record_path(run.get("script"))
        argv = run.get("command_argv")
        inputs, outputs = run.get("inputs"), run.get("outputs")
        status = str(run.get("status") or "").strip().lower()
        if not run_id or script not in ALLOWED_SCRIPTS:
            issues.append({"index": index, "run_id": run_id, "type": "script_not_allowed", "script": script})
        if not isinstance(argv, list) or len(argv) < 2 or not all(isinstance(item, str) and item for item in argv):
            issues.append({"index": index, "run_id": run_id, "type": "command_argv_must_be_nonempty_string_list"})
        else:
            normalized = [_safe_record_path(item) for item in argv]
            if argv[0] not in {"python", "python3"}:
                issues.append({"index": index, "run_id": run_id, "type": "command_argv_requires_python_launcher"})
            if normalized[1] != script:
                issues.append({"index": index, "run_id": run_id, "type": "command_argv_script_mismatch"})
            for argument in normalized[1:]:
                if _path_issue(argument):
                    issues.append({"index": index, "run_id": run_id, "type": "command_argv_contains_unsafe_path", "argument": argument})
                    break
        script_hash = str(run.get("script_sha256") or "").strip().lower()
        script_path = _resolve(root, script)
        if not SHA_RE.fullmatch(script_hash) or not script_path.is_file() or _sha256(script_path) != script_hash:
            issues.append({"index": index, "run_id": run_id, "type": "script_hash_mismatch_or_missing"})
        if status not in RUN_STATUSES:
            issues.append({"index": index, "run_id": run_id, "type": "invalid_run_status"})
        for kind, values in (("input", inputs), ("output", outputs)):
            if not isinstance(values, list) or not values:
                issues.append({"index": index, "run_id": run_id, "type": f"run_{kind}s_must_be_nonempty_list"})
                continue
            for value in values:
                relative = _safe_record_path(value)
                if _path_issue(relative) or relative not in files:
                    issues.append({"index": index, "run_id": run_id, "type": f"run_{kind}_not_registered", "path": relative})
        run_checks.append({"run_id": run_id, "script": script, "status": status})
    status = "verified_ephys_trace_replay_manifest" if not issues else "invalid_ephys_trace_replay_manifest"
    return {
        "status": status, "manifest_id": payload.get("manifest_id"), "n_files": len(files), "n_runs": len(runs),
        "file_checks": file_checks, "run_checks": run_checks, "issues": issues,
        "inference_warning": "This manifest gate establishes file linkage, portable raw-file references and replay metadata only; it does not establish cell identity, rhythm, statistical adequacy or causality.",
    }


def validate_file(path: Path, root: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return validate_payload(json.load(handle), root)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv[1:])
    result = validate_file(args.input, args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "verified_ephys_trace_replay_manifest" else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

