#!/usr/bin/env python3
"""Score an auditable ion-channel evidence table with directness and coverage gates."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
READOUT_MATCHES = {"membrane_potential_or_current", "expression_or_localization", "intracellular_ion_concentration", "behavior_only", "none_or_unverified"}
READOUT_DOMAINS = {
    "membrane_potential_or_current": "electrophysiology_or_membrane_potential_readout",
    "expression_or_localization": "molecular_expression_or_localization",
    "intracellular_ion_concentration": "intracellular_ion_concentration_readout",
    "behavior_only": "behavior_only",
    "none_or_unverified": "unmatched_or_unverified",
}
TRACE_FIELDS = ("class", "organism", "target_cell_scope", "evidence_target_cells", "assay", "readout_match", "evidence_label", "confidence", "keep_drop_reason", "sources", "evidence_notes")
TARGET_CELL_TYPES = (
    "clock_neurons", "LNv", "s-LNv", "l-LNv", "LNd", "DN", "DN1", "DN1p", "DN1a", "DN2", "DN3", "LN_ITP_ambiguous",
)
UNVERIFIED_CELL = "unverified"
CELL_PARENT = {
    "LNv": "clock_neurons", "s-LNv": "LNv", "l-LNv": "LNv", "LNd": "clock_neurons", "DN": "clock_neurons",
    "DN1": "DN", "DN1p": "DN1", "DN1a": "DN1", "DN2": "DN", "DN3": "DN", "LN_ITP_ambiguous": "clock_neurons",
}
_CELL_ALIASES = {"ln_itp": "LN_ITP_ambiguous", "ln(v)": "LNv", "lnvs": "LNv"}
_CELL_BY_CASEFOLD = {token.casefold(): token for token in (*TARGET_CELL_TYPES, UNVERIFIED_CELL)}
_CELL_ORDER = {token: index for index, token in enumerate((*TARGET_CELL_TYPES, UNVERIFIED_CELL))}


def parse_cell_tokens(value: str | None, *, field: str = "evidence_target_cells") -> list[str]:
    """Parse and validate semicolon-separated canonical clock-neuron groups."""
    tokens = [token.strip() for token in re.split(r"[;,|]", value or "") if token.strip()]
    normalized: set[str] = set()
    for token in tokens:
        folded = token.casefold()
        canonical = _CELL_ALIASES.get(folded) or _CELL_BY_CASEFOLD.get(folded)
        if canonical is None:
            raise ValueError(f"{field} contains an unknown cell-group token: {token}")
        normalized.add(canonical)
    if UNVERIFIED_CELL in normalized and len(normalized) > 1:
        raise ValueError(f"{field} cannot mix {UNVERIFIED_CELL} with named cell groups")
    return sorted(normalized, key=lambda token: _CELL_ORDER[token])


def _is_cell_ancestor(ancestor: str, descendant: str) -> bool:
    current = descendant
    while current in CELL_PARENT:
        current = CELL_PARENT[current]
        if current == ancestor:
            return True
    return False


def match_target_cells(
    evidence_cells: str | None,
    requested_cells: list[str] | tuple[str, ...] | str | None,
) -> dict[str, object]:
    """Classify exact, broader, subset, missing, and mismatched cell evidence."""
    requested_values = [requested_cells] if isinstance(requested_cells, str) else requested_cells
    requested_raw = None if requested_values is None else ";".join(requested_values)
    requested = parse_cell_tokens(requested_raw, field="requested_target_cells")
    evidence = parse_cell_tokens(evidence_cells)
    if UNVERIFIED_CELL in requested:
        raise ValueError("requested_target_cells cannot contain unverified")
    output: dict[str, object] = {
        "target_cells_requested": ";".join(requested),
        "evidence_target_cells": ";".join(evidence),
        "target_cells_supported": "",
        "target_cells_partially_supported": "",
        "target_cells_unresolved": "",
        "target_cells_uncovered": "",
    }
    if not requested:
        return {**output, "target_cell_match_status": "not_requested"}
    if not evidence or evidence == [UNVERIFIED_CELL]:
        output["target_cells_uncovered"] = ";".join(requested)
        return {**output, "target_cell_match_status": "missing_evidence"}

    supported: list[str] = []
    partial: list[str] = []
    unresolved: list[str] = []
    uncovered: list[str] = []
    for target in requested:
        if target in evidence:
            supported.append(target)
        elif any(_is_cell_ancestor(target, observed) for observed in evidence):
            partial.append(target)
        elif any(_is_cell_ancestor(observed, target) for observed in evidence):
            unresolved.append(target)
        else:
            uncovered.append(target)

    if len(supported) == len(requested):
        status = "exact"
    elif supported or partial:
        status = "partial"
    elif unresolved:
        status = "unresolved"
    else:
        status = "mismatch"
    output.update({
        "target_cells_supported": ";".join(supported),
        "target_cells_partially_supported": ";".join(partial),
        "target_cells_unresolved": ";".join(unresolved),
        "target_cells_uncovered": ";".join(uncovered),
    })
    return {**output, "target_cell_match_status": status}


def _present(value: str | None) -> bool:
    return (value or "").strip().upper() not in MISSING


def _source_scoped_directness(
    candidate: str,
    evidence_log: list[dict[str, str]],
    target_cells: list[str] | tuple[str, ...] | str | None,
    readout_match: str,
) -> tuple[dict[str, object], dict[str, object]]:
    """Evaluate directness only from checked source-log rows for one readout."""
    if readout_match not in READOUT_MATCHES:
        raise ValueError(f"readout_match must be one of {sorted(READOUT_MATCHES)}: {readout_match}")
    requested_values = [target_cells] if isinstance(target_cells, str) else (target_cells or [])
    requested = parse_cell_tokens(";".join(requested_values), field="requested_target_cells")
    if UNVERIFIED_CELL in requested:
        raise ValueError("requested_target_cells cannot contain unverified")
    domain = READOUT_DOMAINS[readout_match]
    candidates = [
        log_row for log_row in evidence_log
        if (log_row.get("candidate") or "").strip().casefold() == candidate.strip().casefold()
        and (log_row.get("readout_match") or "").strip() == readout_match
        and (log_row.get("source_support_status") or "").strip().lower() == "checked"
    ]

    def evidence_grade(log_row: dict[str, str]) -> int:
        label = (log_row.get("evidence_label") or "").strip().lower()
        target_scope = (log_row.get("target_cell_scope") or "").strip().lower()
        has_assay = _present(log_row.get("assay"))
        if label == "direct" and target_scope == "direct_target_neuron" and has_assay:
            return 3
        if label == "near_direct" and target_scope in {"direct_target_neuron", "nearby_clock_neuron"} and has_assay:
            return 2
        return 0

    def row_cells(log_row: dict[str, str]) -> list[str]:
        try:
            return parse_cell_tokens(log_row.get("evidence_target_cells"))
        except ValueError:
            return []

    eligible = [log_row for log_row in candidates if evidence_grade(log_row) > 0]
    per_target: dict[str, str] = {}
    supported: list[str] = []
    partial: list[str] = []
    unresolved: list[str] = []
    uncovered: list[str] = []
    contributing: set[str] = set()
    if requested:
        for target in requested:
            exact_all = [log_row for log_row in candidates if target in row_cells(log_row)]
            exact_eligible = [log_row for log_row in eligible if target in row_cells(log_row)]
            child_eligible = [
                log_row for log_row in eligible
                if any(_is_cell_ancestor(target, cell) for cell in row_cells(log_row))
            ]
            parent_eligible = [
                log_row for log_row in eligible
                if any(_is_cell_ancestor(cell, target) for cell in row_cells(log_row))
            ]
            if exact_eligible:
                best = max(evidence_grade(log_row) for log_row in exact_eligible)
                per_target[target] = "direct" if best == 3 else "conditional"
                supported.append(target)
                contributing.update(
                    (log_row.get("record_id") or "").strip()
                    for log_row in exact_eligible if evidence_grade(log_row) == best
                )
            elif child_eligible:
                per_target[target] = "partial"
                partial.append(target)
                contributing.update((log_row.get("record_id") or "").strip() for log_row in child_eligible)
            elif parent_eligible:
                per_target[target] = "unresolved"
                unresolved.append(target)
                contributing.update((log_row.get("record_id") or "").strip() for log_row in parent_eligible)
            elif exact_all:
                per_target[target] = "matched_but_not_direct"
                uncovered.append(target)
            else:
                per_target[target] = "missing"
                uncovered.append(target)

        if all(per_target[target] == "direct" for target in requested):
            gate, score = "pass", 3
        elif all(per_target[target] in {"direct", "conditional"} for target in requested):
            gate, score = "conditional", 2
        elif all(per_target[target] == "unresolved" for target in requested):
            gate, score = "conditional_target_cell_scope", 2
        elif any(per_target[target] in {"direct", "conditional", "partial", "unresolved"} for target in requested):
            gate, score = "partial_target_coverage", 1
        else:
            gate, score = "needs_direct_evidence", 0
        has_named_cell_evidence = any(
            (cells := row_cells(log_row)) and cells != [UNVERIFIED_CELL]
            for log_row in candidates
        )
        if all(per_target[target] == "missing" for target in requested) and not has_named_cell_evidence:
            match_status = "missing_evidence"
        elif all(per_target[target] in {"direct", "conditional", "matched_but_not_direct"} for target in requested):
            match_status = "exact"
        elif all(per_target[target] == "unresolved" for target in requested):
            match_status = "unresolved"
        elif any(per_target[target] in {"direct", "conditional", "partial", "unresolved", "matched_but_not_direct"} for target in requested):
            match_status = "partial"
        elif candidates:
            match_status = "mismatch"
        else:
            match_status = "missing_evidence"
    else:
        gate, score, match_status = "needs_target_cell_query", 0, "not_requested"

    source_ids = sorted(record_id for record_id in contributing if record_id)
    basis_by_gate = {
        "pass": f"Checked source-log records directly support the requested target cell(s) for {readout_match}.",
        "conditional": f"Checked source-log records support the requested target cell(s) for {readout_match}, but at least one record is near-direct.",
        "conditional_target_cell_scope": f"Checked {readout_match} evidence names a broader cell group and does not resolve the requested subtype.",
        "partial_target_coverage": f"Checked source-log records cover only part of the requested target-cell set for {readout_match}.",
        "needs_target_cell_query": f"Checked source-log records were filtered to {readout_match}; no target cell was requested.",
        "needs_direct_evidence": f"No checked direct or near-direct source-log record supports the requested target cell(s) for {readout_match}.",
    }
    basis = basis_by_gate[gate]
    if source_ids:
        basis += " Supporting record IDs: " + ";".join(source_ids) + "."
    directness = {
        "directness_score": score,
        "directness_gate": gate,
        "readout_domain": domain,
        "scoring_readout_match": readout_match,
        "directness_source_records": ";".join(source_ids),
        "directness_basis": basis,
    }
    cell_match = {
        "target_cells_requested": ";".join(requested),
        "target_cell_match_status": match_status,
        "target_cells_supported": ";".join(supported),
        "target_cells_partially_supported": ";".join(partial),
        "target_cells_unresolved": ";".join(unresolved),
        "target_cells_uncovered": ";".join(uncovered),
    }
    return directness, cell_match


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
    usable_readout = readout in {
        "membrane_potential_or_current", "expression_or_localization", "intracellular_ion_concentration",
    }
    if label == "direct" and target_direct and has_assay and usable_readout:
        if readout == "expression_or_localization":
            basis = (
                "Directness applies only to the measured target-neuron expression/localization readout; "
                "it does not establish channel current, membrane-potential rhythm, or channel-specific causality."
            )
        elif readout == "intracellular_ion_concentration":
            basis = (
                "Directness applies only to the measured intracellular ion-concentration readout; "
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
        elif readout == "intracellular_ion_concentration":
            basis = "Conditional target-matched intracellular ion-concentration evidence only; not channel-current evidence."
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


def score_row(
    row: dict[str, str],
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    target_cells: list[str] | tuple[str, ...] | str | None = None,
    evidence_log: list[dict[str, str]] | None = None,
    readout_match: str | None = None,
) -> dict[str, object]:
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
    if evidence_log is not None:
        if not readout_match:
            raise ValueError("readout_match is required when source-log directness is enabled")
        if not target_cells:
            raise ValueError("an explicit target-cell query is required when source-log directness is enabled")
        directness, cell_match = _source_scoped_directness(
            row.get("candidate", ""), evidence_log, target_cells, readout_match,
        )
    else:
        if readout_match:
            raise ValueError("a checked source log is required when readout_match is specified")
        directness = dict(_directness(row))
        cell_match = match_target_cells(row.get("evidence_target_cells"), target_cells)
        cell_status = cell_match["target_cell_match_status"]
        if directness["directness_gate"] in {"pass", "conditional"}:
            if cell_status == "not_requested":
                directness.update({
                    "directness_score": 0,
                    "directness_gate": "needs_target_cell_query",
                    "directness_basis": str(directness["directness_basis"]) + " No --target-cell was supplied, so cell-type specificity cannot be evaluated.",
                })
            elif cell_status == "partial":
                directness.update({
                    "directness_score": 1,
                    "directness_gate": "partial_target_coverage",
                    "directness_basis": str(directness["directness_basis"]) + " Evidence covers only a subset of the requested target-cell groups.",
                })
            elif cell_status == "unresolved":
                directness.update({
                    "directness_score": min(2, int(directness["directness_score"])),
                    "directness_gate": "conditional_target_cell_scope",
                    "directness_basis": str(directness["directness_basis"]) + " The evidence names a broader group and does not resolve the requested neuron subtype.",
                })
            elif cell_status != "exact":
                directness.update({
                    "directness_score": 0,
                    "directness_gate": "needs_direct_evidence",
                    "directness_basis": str(directness["directness_basis"]) + " Recorded evidence cells do not match the requested target cell(s).",
                })
    gate = directness["directness_gate"]
    if coverage_gate != "pass":
        shortlist_gate = "needs_evidence"
    elif gate == "pass":
        shortlist_gate = "pass"
    elif gate in {"conditional", "conditional_target_cell_scope"}:
        shortlist_gate = "conditional_directness"
    elif gate == "partial_target_coverage":
        shortlist_gate = "partial_target_coverage"
    elif gate == "needs_target_cell_query":
        shortlist_gate = "needs_target_cell_query"
    else:
        shortlist_gate = "needs_evidence"
    result: dict[str, object] = {
        "candidate": row.get("candidate", ""),
        "score": score,
        "coverage": coverage,
        "coverage_adjusted_score": adjusted,
        "observed_dimensions": observed,
        "coverage_gate": coverage_gate,
        **directness,
        **cell_match,
        "shortlist_gate": shortlist_gate,
    }
    for field in TRACE_FIELDS:
        if field in row:
            result[field] = row.get(field, "")
    return result


def _ranking_key(row: dict[str, object]) -> tuple[object, ...]:
    return (
        row["directness_gate"] == "pass",
        row["directness_score"],
        row["coverage_adjusted_score"] is not None,
        row["coverage_adjusted_score"] if row["coverage_adjusted_score"] is not None else -1,
        row["coverage"],
        row["score"] if row["score"] is not None else -1,
    )


def rank_rows(
    rows: list[dict[str, str]],
    weights: dict[str, float] = DEFAULT_WEIGHTS,
    target_cells: list[str] | tuple[str, ...] | str | None = None,
    evidence_log: list[dict[str, str]] | None = None,
    readout_match: str | None = None,
) -> list[dict[str, object]]:
    scored = [score_row(row, weights, target_cells, evidence_log, readout_match) for row in rows]
    return sorted(scored, key=_ranking_key, reverse=True)


def sensitivity(
    rows: list[dict[str, str]],
    target_cells: list[str] | tuple[str, ...] | str | None = None,
    evidence_log: list[dict[str, str]] | None = None,
    readout_match: str | None = None,
) -> dict[str, object]:
    scenarios = {
        "default": DEFAULT_WEIGHTS,
        "expression_ephys_priority": {**DEFAULT_WEIGHTS, "expression": 6.0, "electrophysiology": 6.0},
        "genetic_tools_priority": {**DEFAULT_WEIGHTS, "genetic_tools": 6.0},
    }
    requested_values = [target_cells] if isinstance(target_cells, str) else (target_cells or [])
    requested = parse_cell_tokens(";".join(requested_values), field="requested_target_cells")
    rankings: dict[str, list[str]] = {}
    gate_pass: dict[str, list[str]] = {}
    conditional: dict[str, list[str]] = {}
    unscored: dict[str, list[str]] = {}
    top_ties: dict[str, list[str]] = {}
    for name, weights in scenarios.items():
        ranked = rank_rows(rows, weights, requested, evidence_log, readout_match)
        scoreable = [row for row in ranked if row["score"] is not None]
        rankings[name] = [str(row["candidate"]) for row in scoreable]
        gate_pass[name] = [str(row["candidate"]) for row in ranked if row["shortlist_gate"] == "pass"]
        conditional[name] = [str(row["candidate"]) for row in ranked if row["shortlist_gate"] == "conditional_directness"]
        unscored[name] = [str(row["candidate"]) for row in ranked if row["score"] is None]
        top_eligible = [row for row in scoreable if row["shortlist_gate"] in {"pass", "conditional_directness"}]
        if not top_eligible:
            top_ties[name] = []
            continue
        best_key = _ranking_key(top_eligible[0])
        top_ties[name] = [str(row["candidate"]) for row in top_eligible if _ranking_key(row) == best_key]
    top_candidates = {name: (values[0] if len(values) == 1 else None) for name, values in top_ties.items()}
    any_scored = any(rankings.values())
    top_values = list(top_candidates.values())
    any_target_scoped_top = any(top_ties.values())
    top_candidate_set_stable = (
        all(top_ties[name] for name in scenarios)
        and len({tuple(sorted(top_ties[name])) for name in scenarios}) == 1
    ) if any_target_scoped_top else None
    top_status = {
        name: ("target_scoped_top_available" if top_ties[name] else ("no_target_scoped_scored_candidates" if rankings[name] else "insufficient_scored_evidence"))
        for name in scenarios
    }
    return {
        "scenarios": list(scenarios),
        "target_cells_requested": requested,
        "readout_match_used": readout_match,
        "directness_source": "checked_evidence_search_log" if evidence_log is not None else "candidate_row_summary",
        "ranking_status": "scored_ranking_available" if any_scored else ("empty_candidate_set" if not rows else "insufficient_scored_evidence"),
        "rankings": rankings,
        "shortlist_gate_pass": gate_pass,
        "conditional_directness": conditional,
        "unscored_candidates": unscored,
        "top_candidates": top_candidates,
        "top_candidate_ties": top_ties,
        "top_candidate_status": top_status,
        "top_candidate_set_stable": top_candidate_set_stable,
        "top_candidate_stable": (len(set(top_values)) == 1 and None not in top_values) if any_target_scoped_top else None,
        "top_candidate_stability_interpretation": (
            "top_candidate_stable means the same unique winner across all weight scenarios; "
            "top_candidate_set_stable means the same non-empty top/tie set across all scenarios. "
            "A stable tie is not a unique winner."
        ),
        "ranking_rule": "rank all scored evidence rows for the long list by target-specific directness, coverage_adjusted_score = score * weighted_coverage, coverage, and raw score; choose Top only among exact-gated or conditional-directness target-scoped rows; unscored, partial-coverage, and mismatched rows cannot become Top; tied tops are reported without an arbitrary single winner",
        "shortlist_gate_rule": (
            f"pass requires direct target-neuron evidence (direct label, target_cell_scope=direct_target_neuron, named assay, "
            f"matched readout), exact evidence_target_cells coverage of every requested --target-cell, coverage >= {MIN_SHORTLIST_COVERAGE}, "
            f"and observed_dimensions >= {MIN_SHORTLIST_DIMENSIONS}; without a requested target cell no direct shortlist pass is assigned; "
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
    parser.add_argument("--target-cell", action="append", choices=TARGET_CELL_TYPES, help="Target neuron group for this ranking; repeat once per requested group. Without it, directness remains unscoped.")
    parser.add_argument("--search-log", type=Path, help="Use source-level assay/readout evidence, rather than pooled candidate-row fields, to calculate target directness.")
    parser.add_argument("--readout-match", choices=sorted(READOUT_MATCHES), help="Readout to evaluate against checked source-log records; requires --search-log and --target-cell.")
    args = parser.parse_args(argv[1:])
    try:
        if bool(args.search_log) != bool(args.readout_match):
            raise ValueError("--search-log and --readout-match must be supplied together")
        if args.search_log and not args.target_cell:
            raise ValueError("--target-cell is required when using --search-log")
        with args.input.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        needs_source_log = any(
            any(_rating(row.get(dimension, "NA")) is not None for dimension in DIMENSIONS)
            or (row.get("readout_match") or "").strip() == "membrane_potential_or_current"
            for row in rows
        )
        if needs_source_log and not args.search_log:
            raise ValueError(
                "--search-log and --readout-match are required for scored evidence or membrane_potential_or_current "
                "candidate tables; candidate-row summaries alone cannot support a real target-specific ranking. "
                "The no-log diagnostic path is restricted to all-NA, non-current context tables."
            )
        evidence_log = None
        if args.search_log:
            from scripts.validate_evidence_search_log import validate as validate_search_log
            from scripts.validate_candidate_evidence import validate as validate_candidate_table

            validation = validate_search_log(args.search_log)
            if validation.get("status") != "verified_evidence_search_log":
                raise ValueError(f"search log failed validation: {validation.get('issues', [])}")
            candidate_validation = validate_candidate_table(args.input, args.search_log)
            if candidate_validation.get("status") != "verified_candidate_evidence_table":
                raise ValueError(
                    "candidate table and search log failed joint validation: "
                    f"{candidate_validation.get('issues', [])}"
                )
            with args.search_log.open(newline="", encoding="utf-8") as handle:
                evidence_log = list(csv.DictReader(handle))
        ranked = rank_rows(rows, target_cells=args.target_cell, evidence_log=evidence_log, readout_match=args.readout_match)
        sens = sensitivity(rows, target_cells=args.target_cell, evidence_log=evidence_log, readout_match=args.readout_match)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        fields = ["candidate", "score", "coverage", "coverage_adjusted_score", "observed_dimensions", "coverage_gate", "directness_score", "directness_gate", "readout_domain", "scoring_readout_match", "directness_source_records", "directness_basis", "target_cells_requested", "target_cell_match_status", "target_cells_supported", "target_cells_partially_supported", "target_cells_unresolved", "target_cells_uncovered", "shortlist_gate", *TRACE_FIELDS]
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
