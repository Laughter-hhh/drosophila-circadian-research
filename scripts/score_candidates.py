#!/usr/bin/env python3
"""Score an auditable ion-channel evidence table with directness and coverage gates."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path


DIMENSIONS = (
    "expression",
    "electrophysiology",
    "genetic_tools",
    "class_match",
    "rhythmic_evidence",
    "fly_causal",
    "cross_species",
)
DEFAULT_WEIGHTS = {
    "expression": 4.0,
    "electrophysiology": 4.0,
    "genetic_tools": 3.0,
    "class_match": 2.0,
    "rhythmic_evidence": 2.0,
    "fly_causal": 1.0,
    "cross_species": 0.5,
}
MIN_SHORTLIST_COVERAGE = 0.5
MIN_SHORTLIST_DIMENSIONS = 3
MISSING = {"", "NA", "N/A", "NAN", "NULL", "UNKNOWN", "NOT_REPORTED", "NOT SPECIFIED", "NOT_AVAILABLE", "NOT APPLICABLE", "NONE REPORTED", "."}
DIRECTNESS_LABELS = {"direct", "near_direct", "indirect", "unverified"}
TARGET_SCOPES = {"direct_target_neuron", "nearby_clock_neuron", "indirect_or_unverified", "none_or_unverified"}
READOUT_MATCHES = {"membrane_potential_or_current", "expression_or_localization", "behavior_only", "none_or_unverified"}
READOUT_DOMAINS = {
    "membrane_potential_or_current": "electrophysiology_or_membrane_potential_readout",
    "expression_or_localization": "molecular_expression_or_localization",
    "behavior_only": "behavior_only",
    "none_or_unverified": "unmatched_or_unverified",
}
TRACE_FIELDS = ("class", "organism", "target_cell_scope", "assay", "readout_match", "evidence_label", "confidence", "keep_drop_reason", "sources", "evidence_notes")


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _rating(value: str) -> float | None:
    token = value.strip().upper()
    if token in MISSING:
        return None
    try:
        number = float(token)
    except ValueError as exc:
        raise ValueError(f"rating is not numeric or NA: {value}") from exc
    if not math.isfinite(number) or number < 0 or number > 3:
        raise ValueError(f"rating must be between 0 and 3: {value}")
    return number


def _directness(row: dict[str, str]) -> dict[str, object]:
    label = (row.get("evidence_label") or "").strip().lower()
    target = (row.get("target_cell_scope") or "").strip().lower()
    readout = (row.get("readout_match") or "").strip().lower()
    if not label or label.upper() in MISSING:
        return {
            "directness_score": 0,
            "directness_gate": "needs_direct_evidence",
            "readout_domain": READOUT_DOMAINS.get(readout, "unmatched_or_unverified"),
            "directness_basis": "evidence_label is missing; the recorded readout domain does not establish directness.",
        }
    if label not in DIRECTNESS_LABELS:
        raise ValueError(f"evidence_label must be one of {sorted(DIRECTNESS_LABELS)}: {label}")
    if target and target not in TARGET_SCOPES:
        raise ValueError(f"target_cell_scope must be one of {sorted(TARGET_SCOPES)}: {target}")
    if readout and readout not in READOUT_MATCHES:
        raise ValueError(f"readout_match must be one of {sorted(READOUT_MATCHES)}: {readout}")
    domain = READOUT_DOMAINS.get(readout, "unmatched_or_unverified")
    has_assay = _present(row.get("assay"))
    target_direct = target == "direct_target_neuron"
    usable_readout = readout in {"membrane_potential_or_current", "expression_or_localization"}
    if label == "direct" and target_direct and has_assay and usable_readout:
        if readout == "expression_or_localization":
            basis = (
                "Directness applies only to the measured target-neuron expression/localization readout; "
                "it does not establish channel current, membrane-potential rhythm, or channel-specific causality."
            )
        else:
            basis = (
                "Directness applies only to the matched target-neuron current/membrane-potential readout; "
                "candidate-specific causality still requires a documented perturbation and appropriate controls."
            )
        return {"directness_score": 3, "directness_gate": "pass", "readout_domain": domain, "directness_basis": basis}
    if label == "near_direct" and target in {"direct_target_neuron", "nearby_clock_neuron"} and has_assay and usable_readout:
        if readout == "expression_or_localization":
            basis = "Conditional target-matched expression/localization evidence only; pilot-level, not direct channel-function evidence."
        else:
            basis = "Conditional current/membrane-potential readout; pilot-level, and causality requires candidate perturbation and controls."
        return {"directness_score": 2, "directness_gate": "conditional", "readout_domain": domain, "directness_basis": basis}
    if label == "indirect":
        return {
            "directness_score": 1,
            "directness_gate": "needs_direct_evidence",
            "readout_domain": domain,
            "directness_basis": "indirect evidence is hypothesis-generating only for this target-neuron screen.",
        }
    return {
        "directness_score": 0,
        "directness_gate": "needs_direct_evidence",
        "readout_domain": domain,
        "directness_basis": "target cell, assay, readout, or evidence label does not support a direct target-neuron claim.",
    }


def score_row(row: dict[str, str], weights: dict[str, float] = DEFAULT_WEIGHTS) -> dict[str, object]:
    numerator = 0.0
    denominator = 0.0
    observed = 0
    for dimension in DIMENSIONS:
        rating = _rating(row.get(dimension, "NA"))
        if rating is None:
            continue
        weight = weights[dimension]
        numerator += rating * weight
        denominator += 3.0 * weight
        observed += 1
    score = None if denominator == 0 else 100.0 * numerator / denominator
    coverage = sum(weights[d] for d in DIMENSIONS if _rating(row.get(d, "NA")) is not None) / sum(weights.values())
    adjusted = None if score is None else score * coverage
    coverage_gate = "pass" if coverage >= MIN_SHORTLIST_COVERAGE and observed >= MIN_SHORTLIST_DIMENSIONS else "needs_evidence"
    directness = _directness(row)
    shortlist_gate = "pass" if coverage_gate == "pass" and directness["directness_gate"] == "pass" else ("conditional_directness" if coverage_gate == "pass" and directness["directness_gate"] == "conditional" else "needs_evidence")
    result: dict[str, object] = {
        "candidate": row.get("candidate", ""),
        "score": score,
        "coverage": coverage,
        "coverage_adjusted_score": adjusted,
        "observed_dimensions": observed,
        "coverage_gate": coverage_gate,
        **directness,
        "shortlist_gate": shortlist_gate,
    }
    for field in TRACE_FIELDS:
        if field in row:
            result[field] = row.get(field, "")
    return result


def rank_rows(rows: list[dict[str, str]], weights: dict[str, float] = DEFAULT_WEIGHTS) -> list[dict[str, object]]:
    scored = [score_row(row, weights) for row in rows]
    return sorted(
        scored,
        key=lambda row: (
            row["directness_gate"] == "pass",
            row["directness_score"],
            row["coverage_adjusted_score"] is not None,
            row["coverage_adjusted_score"] or -1,
            row["coverage"],
            row["score"] or -1,
        ),
        reverse=True,
    )


def sensitivity(rows: list[dict[str, str]]) -> dict[str, object]:
    scenarios = {
        "default": DEFAULT_WEIGHTS,
        "expression_ephys_priority": {**DEFAULT_WEIGHTS, "expression": 6.0, "electrophysiology": 6.0},
        "genetic_tools_priority": {**DEFAULT_WEIGHTS, "genetic_tools": 6.0},
    }
    rankings = {}
    gate_pass = {}
    conditional = {}
    for name, weights in scenarios.items():
        ranked = rank_rows(rows, weights)
        rankings[name] = [row["candidate"] for row in ranked]
        gate_pass[name] = [row["candidate"] for row in ranked if row["shortlist_gate"] == "pass"]
        conditional[name] = [row["candidate"] for row in ranked if row["shortlist_gate"] == "conditional_directness"]
    top_candidates = {name: values[0] if values else None for name, values in rankings.items()}
    return {
        "scenarios": list(scenarios),
        "rankings": rankings,
        "shortlist_gate_pass": gate_pass,
        "conditional_directness": conditional,
        "top_candidates": top_candidates,
        "top_candidate_stable": len(set(value for value in top_candidates.values() if value is not None)) <= 1,
        "ranking_rule": "sort by directness gate/score first, then coverage_adjusted_score = raw_score * weighted_coverage, then coverage and raw_score",
        "shortlist_gate_rule": (
            f"pass requires direct target-neuron evidence (direct label, target_cell_scope=direct_target_neuron, named assay, "
            f"matched readout), coverage >= {MIN_SHORTLIST_COVERAGE}, and observed_dimensions >= {MIN_SHORTLIST_DIMENSIONS}; "
            "directness is specific to the matched readout: transcript/localization evidence is not channel-function evidence, "
            "and current/membrane-potential observations alone do not establish candidate-specific causality without perturbation and controls"
        ),
        "inference_warning": "Ranking is an evidence triage aid, not a biological conclusion; source support and reagent identity require independent audit.",
    }


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--sensitivity-output", type=Path)
    args = parser.parse_args(argv[1:])
    try:
        with args.input.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        ranked = rank_rows(rows)
        sens = sensitivity(rows)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = ["candidate", "score", "coverage", "coverage_adjusted_score", "observed_dimensions", "coverage_gate", "directness_score", "directness_gate", "readout_domain", "directness_basis", "shortlist_gate", *TRACE_FIELDS]
        with args.output.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(ranked)
    else:
        print(json.dumps(ranked, ensure_ascii=False, indent=2))
    if args.sensitivity_output:
        args.sensitivity_output.parent.mkdir(parents=True, exist_ok=True)
        args.sensitivity_output.write_text(json.dumps(sens, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
