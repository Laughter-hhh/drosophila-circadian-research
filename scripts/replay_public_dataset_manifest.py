#!/usr/bin/env python3
"""Replay a validated public-data manifest in an isolated temporary mirror.

Only reviewed repository analysis scripts are allowed. The runner never shells
out through the human-readable ``command`` field; it uses structured
``command_argv`` arrays, substitutes the current Python interpreter, and compares
each declared output SHA-256 against the manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from scripts.validate_public_dataset_manifest import _is_safe_relative, _norm_rel, _resolve, _sha256, validate_file
except ModuleNotFoundError:  # direct execution as ``python scripts/replay_public_dataset_manifest.py``
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.validate_public_dataset_manifest import _is_safe_relative, _norm_rel, _resolve, _sha256, validate_file


ALLOWED_SCRIPTS = {
    "scripts/parse_geo_series_matrix.py",
    "scripts/extract_gene_expression.py",
    "scripts/analyze_expression_rhythm.py",
    "scripts/analyze_cosinor_inference.py",
    "scripts/audit_public_behavior_metadata.py",
    "scripts/extract_published_sc_clock_channel_rhythms.py",
    "scripts/audit_gse157504_candidate_detection.py",
    "scripts/build_gse157504_candidate_evidence.py",
    "scripts/validate_evidence_search_log.py",
    "scripts/validate_candidate_evidence.py",
    "scripts/score_candidates.py",
}


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_argv(run: dict[str, Any]) -> tuple[list[str] | None, dict[str, Any] | None]:
    run_id = str(run.get("run_id") or "").strip()
    raw = run.get("command_argv")
    if not isinstance(raw, list) or len(raw) < 2 or not all(isinstance(item, str) and item for item in raw):
        return None, {"run_id": run_id, "type": "command_argv_must_be_nonempty_string_list"}
    if raw[0] not in {"python", "python3"}:
        return None, {"run_id": run_id, "type": "command_argv_requires_python_launcher"}
    script = _norm_rel(raw[1])
    declared = _norm_rel(run.get("script"))
    if script != declared or script not in ALLOWED_SCRIPTS:
        return None, {"run_id": run_id, "type": "command_argv_script_not_allowed", "script": script}
    for arg in raw[1:]:
        normalized = _norm_rel(arg)
        if "\x00" in arg or not _is_safe_relative(normalized):
            return None, {"run_id": run_id, "type": "command_argv_contains_unsafe_path", "argument": arg}
    return list(raw), None


def _copy_input_tree(source_root: Path, replay_root: Path, payload: dict[str, Any]) -> None:
    shutil.copytree(
        source_root / "scripts",
        replay_root / "scripts",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    produced = {
        _norm_rel(path)
        for run in payload.get("runs", [])
        if isinstance(run, dict)
        for path in (run.get("outputs") or [])
    }
    for record in payload.get("files", []):
        if not isinstance(record, dict):
            continue
        relative = _norm_rel(record.get("path"))
        if relative in produced:
            continue
        source = _resolve(source_root, relative)
        destination = _resolve(replay_root, relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def replay_payload(payload: dict[str, Any], source_root: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    manifest_issues: list[dict[str, Any]] = []
    files_by_path = {
        _norm_rel(record.get("path")): record
        for record in payload.get("files", [])
        if isinstance(record, dict)
    }
    run_reports: list[dict[str, Any]] = []
    output_checks: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        if isinstance(run, dict):
            _, issue = _safe_argv(run)
            if issue:
                manifest_issues.append(issue)
        else:
            manifest_issues.append({"type": "run_record_must_be_object"})
    if manifest_issues:
        return {
            "status": "blocked_public_dataset_replay",
            "issues": manifest_issues,
            "runs": [],
            "output_checks": [],
            "inference_warning": "No command was executed because the replay argv gate failed.",
        }

    with tempfile.TemporaryDirectory(prefix="drosophila-public-replay-") as temporary:
        replay_root = Path(temporary)
        _copy_input_tree(source_root, replay_root, payload)
        for run in payload.get("runs", []):
            assert isinstance(run, dict)
            argv, argv_issue = _safe_argv(run)
            assert argv is not None and argv_issue is None
            run_id = str(run.get("run_id") or "")
            script_relative = _norm_rel(run.get("script"))
            command = [sys.executable, str(_resolve(replay_root, script_relative)), *argv[2:]]
            environment = dict(os.environ)
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            try:
                completed = subprocess.run(
                    command,
                    cwd=replay_root,
                    text=True,
                    capture_output=True,
                    timeout=timeout_seconds,
                    check=False,
                    env=environment,
                )
                run_report = {
                    "run_id": run_id,
                    "returncode": completed.returncode,
                    "stdout_sha256": _digest_text(completed.stdout),
                    "stderr_sha256": _digest_text(completed.stderr),
                    "stdout_preview": completed.stdout[-1000:],
                    "stderr_preview": completed.stderr[-1000:],
                }
            except subprocess.TimeoutExpired as exc:
                run_report = {
                    "run_id": run_id,
                    "returncode": None,
                    "type": "run_timeout",
                    "timeout_seconds": timeout_seconds,
                    "stdout_preview": (exc.stdout or "")[-1000:] if isinstance(exc.stdout, str) else "",
                    "stderr_preview": (exc.stderr or "")[-1000:] if isinstance(exc.stderr, str) else "",
                }
            run_reports.append(run_report)
            if run_report.get("returncode") != 0:
                issues.append({"run_id": run_id, "type": "run_nonzero_exit", "returncode": run_report.get("returncode")})
                break
            for raw_output in run.get("outputs") or []:
                relative = _norm_rel(raw_output)
                expected_record = files_by_path.get(relative, {})
                expected_hash = str(expected_record.get("sha256") or "").lower()
                output = _resolve(replay_root, relative)
                check: dict[str, Any] = {"run_id": run_id, "path": relative, "expected_sha256": expected_hash}
                if not output.is_file():
                    check["status"] = "missing_after_replay"
                    issues.append({"run_id": run_id, "type": "declared_output_missing_after_replay", "path": relative})
                else:
                    observed_hash = _sha256(output)
                    check["observed_sha256"] = observed_hash
                    if observed_hash != expected_hash:
                        check["status"] = "hash_mismatch_after_replay"
                        issues.append({"run_id": run_id, "type": "output_hash_mismatch_after_replay", "path": relative, "expected": expected_hash, "observed": observed_hash})
                    else:
                        check["status"] = "replay_hash_verified"
                output_checks.append(check)
            if issues:
                break

    return {
        "status": "verified_public_dataset_replay" if not issues else "blocked_public_dataset_replay",
        "n_runs": len(run_reports),
        "n_output_checks": len(output_checks),
        "runs": run_reports,
        "output_checks": output_checks,
        "issues": issues,
        "inference_warning": "Replay verifies deterministic execution and declared output hashes in an isolated temporary mirror; it does not establish biological validity, normalization suitability, statistical adequacy or causal conclusions.",
    }


def replay_file(manifest_path: Path, source_root: Path, timeout_seconds: int = 120) -> dict[str, Any]:
    validation = validate_file(manifest_path, source_root)
    if validation.get("status") != "verified_public_dataset_manifest":
        return {
            "status": "blocked_public_dataset_replay",
            "manifest_validation": validation,
            "issues": [{"type": "manifest_validation_failed"}],
            "runs": [],
            "output_checks": [],
            "inference_warning": "No command was executed because the source manifest did not pass integrity validation.",
        }
    with manifest_path.open(encoding="utf-8") as handle:
        payload = json.load(handle)
    result = replay_payload(payload, source_root, timeout_seconds)
    result["manifest_validation"] = validation
    return result


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="repository root used to resolve relative paths")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    try:
        result = replay_file(args.input, args.root, args.timeout_seconds)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] == "verified_public_dataset_replay" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
