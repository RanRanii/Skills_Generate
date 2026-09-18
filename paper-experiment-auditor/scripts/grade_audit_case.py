#!/usr/bin/env python3
"""Grade one audit summary against a behavioral evaluation oracle."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from validate_audit_output import load_json, validate_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_directory", type=Path)
    parser.add_argument("audit_summary", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def evidence_path_exists(case_dir: Path, item: dict[str, Any]) -> bool:
    if item.get("type") == "RUNTIME":
        artifact = item.get("artifact")
        if artifact is None:
            return bool(item.get("command")) and isinstance(item.get("exit_status"), int)
        relative = Path(str(artifact).replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts:
            return False
        candidates = [case_dir / relative]
        if relative.parts and relative.parts[0] != "repository":
            candidates.append(case_dir / "repository" / relative)
        return any(path.is_file() for path in candidates)
    relative = Path(str(item.get("path", "")).replace("\\", "/"))
    candidates = [case_dir / relative]
    if relative.parts and relative.parts[0] != "repository":
        candidates.append(case_dir / "repository" / relative)
    return any(path.is_file() for path in candidates)


def finding_match_score(
    finding: dict[str, Any],
    requirement: dict[str, Any],
    claims: dict[str, dict[str, Any]],
    evidence: dict[str, dict[str, Any]],
) -> tuple[int, dict[str, bool]]:
    linked_claims = [claims[item] for item in finding.get("claim_ids", []) if item in claims]
    linked_evidence = [evidence[item] for item in finding.get("evidence_ids", []) if item in evidence]
    statuses = {item.get("status") for item in linked_claims}
    evidence_types = {item.get("type") for item in linked_evidence}
    evidence_paths = [str(item.get("path", "")).replace("\\", "/") for item in linked_evidence]
    fixture_paths = [
        fragment.removeprefix("repository/").replace("\\", "/")
        for fragment in requirement["fixture_paths"]
    ]
    checks = {
        "status": bool(statuses & set(requirement["allowed_claim_statuses"])),
        "severity": finding.get("severity") in requirement["allowed_severities"],
        "evidence_types": set(requirement["required_evidence_types"]).issubset(evidence_types),
        "evidence_paths": all(
            any(path.endswith(fragment) or fragment in path for path in evidence_paths)
            for fragment in fixture_paths
        ),
    }
    return sum(checks.values()), checks


def grade_case(case_dir: Path, report: dict[str, Any]) -> dict[str, Any]:
    # Keep structural validation separate from fixture path existence so a
    # hallucinated artifact is scored as a behavioral failure, not malformed
    # JSON. The grader reports the path failure explicitly below.
    validation = validate_report(report)
    if not validation["valid"]:
        return {
            "valid_input": False,
            "status": "INVALID",
            "score": 0,
            "blocking_failures": ["audit summary failed schema validation"],
            "validation": validation,
        }

    manifest = load_json(case_dir / "case.json")
    oracle = load_json(case_dir / "oracle.json")
    claims = {item["claim_id"]: item for item in report["claims"]}
    evidence = {item["evidence_id"]: item for item in report["evidence"]}
    findings = report["findings"]
    by_category: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        by_category.setdefault(finding["category"], []).append(finding)

    required = oracle["required_findings"]
    requirement_results: list[dict[str, Any]] = []
    blocking_failures: list[str] = []
    detection_hits = status_hits = severity_hits = evidence_hits = 0

    for requirement in required:
        category = requirement["category"]
        candidates = by_category.get(category, [])
        if not candidates:
            result = {"category": category, "detected": False, "checks": {}}
            requirement_results.append(result)
            if requirement.get("blocking"):
                blocking_failures.append(f"missed blocking required finding: {category}")
            continue
        detection_hits += 1
        ranked = [
            (finding_match_score(item, requirement, claims, evidence), item)
            for item in candidates
        ]
        (match_points, checks), selected = max(ranked, key=lambda pair: pair[0][0])
        status_hits += int(checks["status"])
        severity_hits += int(checks["severity"])
        evidence_hits += int(checks["evidence_types"] and checks["evidence_paths"])
        requirement_results.append(
            {
                "category": category,
                "detected": True,
                "finding_id": selected["finding_id"],
                "checks": checks,
                "matched_checks": match_points,
            }
        )

    denominator = len(required) or 1
    if not required:
        detection_hits = status_hits = severity_hits = evidence_hits = 1

    forbidden_categories = sorted(
        set(oracle["forbidden_categories"]) & {item["category"] for item in findings}
    )
    forbidden_severities = [
        item["finding_id"]
        for item in findings
        if item["severity"] in set(oracle["forbidden_severities"])
    ]
    required_categories = {item["category"] for item in required}
    high_false_positives = [
        item["finding_id"]
        for item in findings
        if item["category"] not in required_categories and item["severity"] in {"BLOCKER", "MAJOR"}
    ]
    hallucinated_evidence = [
        item["evidence_id"] for item in evidence.values() if not evidence_path_exists(case_dir, item)
    ]

    if forbidden_categories:
        blocking_failures.append(f"forbidden finding categories: {', '.join(forbidden_categories)}")
    if forbidden_severities:
        blocking_failures.append(f"forbidden severities used by: {', '.join(forbidden_severities)}")
    if len(high_false_positives) > oracle["max_high_severity_false_positives"]:
        blocking_failures.append(
            "high-severity false positives exceed limit: " + ", ".join(high_false_positives)
        )
    if hallucinated_evidence:
        blocking_failures.append("evidence paths do not exist in fixture: " + ", ".join(hallucinated_evidence))

    decision = report.get("release_decision")
    readiness = decision.get("status") if isinstance(decision, dict) else report.get("release_readiness")
    readiness_ok = readiness in oracle["expected_release_readiness"]
    if not readiness_ok:
        blocking_failures.append(
            f"release readiness {readiness} not in expected set"
        )

    dimension_scores = {
        "required_detection": round(35 * detection_hits / denominator, 2),
        "claim_status": round(20 * status_hits / denominator, 2),
        "evidence_quality": round(20 * evidence_hits / denominator, 2),
        "severity": round(10 * severity_hits / denominator, 2),
        "conclusion_boundary": 10 if readiness_ok and not validation["warnings"] else 5 if readiness_ok else 0,
        "completeness": 5 if report["claims"] else 0,
    }
    penalty = min(40, 20 * len(forbidden_categories) + 20 * len(forbidden_severities) + 20 * len(high_false_positives))
    score = max(0.0, round(sum(dimension_scores.values()) - penalty, 2))
    passed = score >= 85 and not blocking_failures

    return {
        "valid_input": True,
        "case_id": manifest["case_id"],
        "status": "PASS" if passed else "FAIL",
        "score": score,
        "dimension_scores": dimension_scores,
        "penalty": penalty,
        "requirements": requirement_results,
        "forbidden_categories_found": forbidden_categories,
        "forbidden_severity_findings": forbidden_severities,
        "high_severity_false_positives": high_false_positives,
        "hallucinated_evidence": hallucinated_evidence,
        "blocking_failures": blocking_failures,
        "validation_warnings": validation["warnings"],
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Behavioral evaluation result",
        "",
        f"- Status: `{result['status']}`",
        f"- Score: {result['score']}",
        f"- Case: {result.get('case_id', 'unknown')}",
        "",
        "## Blocking failures",
        "",
    ]
    failures = result.get("blocking_failures", [])
    lines.extend(f"- {item}" for item in failures)
    if not failures:
        lines.append("- None")
    lines.extend(["", "## Dimension scores", "", "| Dimension | Score |", "|---|---:|"])
    for key, value in result.get("dimension_scores", {}).items():
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        if not args.case_directory.is_dir():
            raise ValueError(f"case directory does not exist: {args.case_directory}")
        report = load_json(args.audit_summary)
        result = grade_case(args.case_directory, report)
        rendered = (
            json.dumps(result, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else markdown_report(result)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        if result["status"] == "PASS":
            return 0
        return 2 if result["status"] == "INVALID" else 1
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
