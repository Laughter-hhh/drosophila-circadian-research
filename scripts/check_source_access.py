#!/usr/bin/env python3
"""Check read-only online source accessibility and expected-token visibility."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REQUIRED = {"record_id", "source_url", "expected_tokens"}
MISSING = {"", "NA", "N/A", "UNKNOWN", "NOT_REPORTED"}
HTTP_OK = {200, 203, 206}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _tokens(value: str | None) -> list[str]:
    return [
        token.strip().lower()
        for token in re.split(r"[;,]", value or "")
        if token.strip() and token.strip().upper() not in MISSING
    ]


def _safe_url(value: str) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return False, "source_url must be an absolute HTTP(S) URL"
    if parsed.username or parsed.password:
        return False, "source_url must not contain credentials"
    return True, ""


def _fetch(url: str, timeout: float, max_bytes: int) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "drosophila-circadian-research-source-audit/1.0",
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.8,*/*;q=0.1",
        },
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", response.getcode()))
            body = response.read(max_bytes)
            return {
                "http_status": status,
                "final_url": response.geturl(),
                "content_type": response.headers.get("Content-Type", ""),
                "bytes_read": len(body),
                "body_sha256": hashlib.sha256(body).hexdigest(),
                "body": body.decode("utf-8", errors="replace"),
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read(max_bytes)
        except OSError:
            pass
        return {
            "http_status": int(exc.code),
            "final_url": getattr(exc, "url", url),
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "bytes_read": len(body),
            "body_sha256": hashlib.sha256(body).hexdigest() if body else "",
            "body": body.decode("utf-8", errors="replace"),
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": str(exc),
        }
    except (OSError, TimeoutError, ValueError) as exc:
        return {
            "http_status": None,
            "final_url": url,
            "content_type": "",
            "bytes_read": 0,
            "body_sha256": "",
            "body": "",
            "elapsed_seconds": round(time.monotonic() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def validate(path: Path, timeout: float = 15.0, max_bytes: int = 200_000) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    warnings: list[dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(REQUIRED - set(reader.fieldnames or []))
        if missing:
            return {
                "status": "invalid_source_access_manifest",
                "formal_status": "blocked_by_validation_issues",
                "n_rows": 0,
                "issues": [{"type": "missing_columns", "columns": missing}],
            }
        rows = list(reader)
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    for line_number, row in enumerate(rows, start=2):
        record_id = (row.get("record_id") or "").strip()
        source_url = (row.get("source_url") or "").strip()
        expected = _tokens(row.get("expected_tokens"))
        if not record_id:
            issues.append({"line": line_number, "type": "missing_record_id"})
            continue
        if record_id in seen:
            issues.append({"line": line_number, "record_id": record_id, "type": "duplicate_record_id"})
            continue
        seen.add(record_id)
        valid_url, url_error = _safe_url(source_url)
        if not valid_url:
            issues.append({"line": line_number, "record_id": record_id, "type": "invalid_source_url", "message": url_error})
            continue
        if not expected:
            issues.append({"line": line_number, "record_id": record_id, "type": "missing_expected_tokens"})
            continue
        fetched = _fetch(source_url, timeout, max_bytes)
        status = fetched.get("http_status")
        body = str(fetched.pop("body", ""))
        matched = [token for token in expected if token in body.lower()]
        if status is None or status >= 400:
            access_status = "blocked_http_or_network"
            issues.append({
                "line": line_number,
                "record_id": record_id,
                "type": "source_not_reachable",
                "http_status": status,
                "error": fetched.get("error", ""),
            })
        elif not matched:
            access_status = "reachable_content_unverified"
            warnings.append({
                "line": line_number,
                "record_id": record_id,
                "type": "source_content_token_not_found",
                "http_status": status,
                "expected_tokens": expected,
            })
        else:
            access_status = "reachable_content_verified"
        records.append({
            "line": line_number,
            "record_id": record_id,
            "source_url": source_url,
            "final_url": fetched.get("final_url", source_url),
            "http_status": status,
            "content_type": fetched.get("content_type", ""),
            "bytes_read": fetched.get("bytes_read", 0),
            "body_sha256": fetched.get("body_sha256", ""),
            "expected_tokens": expected,
            "matched_tokens": matched,
            "access_status": access_status,
            "elapsed_seconds": fetched.get("elapsed_seconds", 0),
        })
    if issues:
        status = "blocked_source_access"
        formal_status = "blocked_by_online_access"
    elif warnings:
        status = "conditional_source_access"
        formal_status = "blocked_online_content_not_verified"
    elif records:
        status = "verified_source_access"
        formal_status = "online_content_verified"
    else:
        status = "invalid_source_access_manifest"
        formal_status = "blocked_by_validation_issues"
    return {
        "status": status,
        "formal_status": formal_status,
        "n_rows": len(rows),
        "n_records": len(records),
        "issues": issues,
        "warnings": warnings,
        "records": records,
        "inference_warning": "A reachable page and token match support source-access traceability only; they do not prove the page is current, the genotype is correct, the stock is available, or the cited source supports the biological claim.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="CSV with record_id, source_url and expected_tokens.")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--max-bytes", type=int, default=200_000)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        if args.timeout <= 0 or args.max_bytes <= 0:
            raise ValueError("--timeout and --max-bytes must be positive")
        result = validate(args.input, args.timeout, args.max_bytes)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    return 0 if result["status"] in {"verified_source_access", "conditional_source_access"} else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
