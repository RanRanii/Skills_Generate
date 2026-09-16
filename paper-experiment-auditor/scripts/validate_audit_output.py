#!/usr/bin/env python3
"""Validate a machine-readable paper experiment audit summary."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any


CLAIM_STATUSES = {
    "VERIFIED",
    "CONSISTENT",
    "MISMATCH",
    "UNVERIFIABLE",
    "AMBIGUOUS",
    "NOT_APPLICABLE",
}
EVIDENCE_TYPES = {"PAPER", "CODE", "CONFIG", "ARTIFACT", "RUNTIME", "DOC"}
SEVERITIES = {"BLOCKER", "MAJOR", "MODERATE", "MINOR", "INFO"}
RELEASE_STATUSES = {"READY", "CONDITIONAL", "BLOCKED", "UNKNOWN"}
AUDIT_PROFILES = {"TRIAGE", "STATIC_AUDIT", "REPRODUCTION", "REMEDIATION", "RELEASE_REVIEW"}
CLAIM_TYPES = {"DATA", "METHOD", "TRAINING", "METRIC", "RESULT", "RELEASE"}
CRITICALITIES = {"CORE", "SUPPORTING", "OPERATIONAL"}
EVIDENCE_STRENGTHS = {"DIRECT", "INDIRECT", "SUPPORTING"}
GENERATED_BY = {"HUMAN", "SCRIPT", "COMMAND"}
DISPOSITIONS = {"OPEN", "FIXED", "ACCEPTED_RISK", "WAIVED"}
ID_PATTERNS = {
    "claim_id": re.compile(r"^CLM-\d{3,}$"),
    "evidence_id": re.compile(r"^EVD-\d{3,}$"),
    "finding_id": re.compile(r"^FND-\d{3,}$"),
}
CATEGORY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-fA-F]{64}$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_summary", type=Path, help="audit-summary.json to validate")
    parser.add_argument("--repo-root", type=Path, help="Verify evidence paths exist under this repository root")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write validation report to this file")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"file does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def relative_evidence_path(value: Any) -> bool:
    if not nonempty_string(value):
        return False
    text = str(value).replace("\\", "/")
    if text.startswith("/") or text.startswith("//") or WINDOWS_ABSOLUTE.match(text):
        return False
    return ".." not in PurePosixPath(text).parts


def add_required_string_errors(item: dict[str, Any], fields: tuple[str, ...], prefix: str, errors: list[str]) -> None:
    for field in fields:
        if not nonempty_string(item.get(field)):
            errors.append(f"{prefix}.{field} must be a non-empty string")


def enum_field(item: dict[str, Any], field: str, allowed: set[str], prefix: str, errors: list[str]) -> None:
    """Validate an optional enum field when it is present."""
    value = item.get(field)
    if value is not None and value not in allowed:
        errors.append(f"{prefix}.{field} must be one of {sorted(allowed)}")


def validate_ids(
    items: Any,
    field: str,
    label: str,
    errors: list[str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if not isinstance(items, list):
        errors.append(f"{label} must be an array")
        return [], {}
    valid_items: list[dict[str, Any]] = []
    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        prefix = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        valid_items.append(item)
        identifier = item.get(field)
        if not nonempty_string(identifier) or not ID_PATTERNS[field].fullmatch(str(identifier)):
            errors.append(f"{prefix}.{field} has an invalid format")
            continue
        if identifier in indexed:
            errors.append(f"duplicate {field}: {identifier}")
        indexed[str(identifier)] = item
    return valid_items, indexed


def string_list(value: Any, prefix: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(nonempty_string(item) for item in value):
        errors.append(f"{prefix} must be an array of non-empty strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{prefix} must not contain duplicate values")
    return [str(item) for item in value]


def validate_report(data: Any, repo_root: Path | None = None) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["audit summary must be a JSON object"], "warnings": []}

    version = str(data.get("schema_version"))
    if version not in {"1.0", "0.3"}:
        errors.append("schema_version must be '1.0' (or '0.3' for backward compatibility)")
    is_v1 = version == "1.0"
    if not is_v1:
        warnings.append("schema_version '0.3' is deprecated; upgrade to '1.0'")

    if not nonempty_string(data.get("audit_id")):
        errors.append("audit_id must be a non-empty string")

    subject = data.get("subject") if is_v1 else data.get("scope")
    subject_label = "subject" if is_v1 else "scope"
    if not isinstance(subject, dict):
        errors.append(f"{subject_label} must be an object")
    else:
        add_required_string_errors(subject, ("manuscript", "repository", "commit"), subject_label, errors)

    if is_v1:
        profile = data.get("audit_profile")
        if profile not in AUDIT_PROFILES:
            errors.append(f"audit_profile must be one of {sorted(AUDIT_PROFILES)}")

    claims, claim_index = validate_ids(data.get("claims"), "claim_id", "claims", errors)
    evidence, evidence_index = validate_ids(data.get("evidence"), "evidence_id", "evidence", errors)
    findings, finding_index = validate_ids(data.get("findings"), "finding_id", "findings", errors)

    for index, item in enumerate(evidence):
        prefix = f"evidence[{index}]"
        evidence_type = item.get("type")
        if evidence_type not in EVIDENCE_TYPES:
            errors.append(f"{prefix}.type must be one of {sorted(EVIDENCE_TYPES)}")
            continue
        add_required_string_errors(item, ("observation",), prefix, errors)
        if is_v1:
            enum_field(item, "strength", EVIDENCE_STRENGTHS, prefix, errors)
            enum_field(item, "generated_by", GENERATED_BY, prefix, errors)
            digest = item.get("digest")
            if digest is not None and (not isinstance(digest, str) or not DIGEST_PATTERN.fullmatch(digest)):
                errors.append(f"{prefix}.digest must be a sha256:<64-hex> string")
        if evidence_type == "RUNTIME":
            if is_v1:
                add_required_string_errors(item, ("command", "commit", "artifact"), prefix, errors)
                exit_status = item.get("exit_status")
                if not isinstance(exit_status, int) or isinstance(exit_status, bool):
                    errors.append(f"{prefix}.exit_status must be an integer")
                if item.get("artifact") is not None and not relative_evidence_path(item.get("artifact")):
                    errors.append(f"{prefix}.artifact must be a safe relative path")
            else:
                add_required_string_errors(item, ("path", "locator"), prefix, errors)
        else:
            add_required_string_errors(item, ("path", "locator"), prefix, errors)
            if item.get("path") is not None and not relative_evidence_path(item.get("path")):
                errors.append(f"{prefix}.path must be a safe relative path")

    for index, item in enumerate(findings):
        prefix = f"findings[{index}]"
        category = item.get("category")
        if not nonempty_string(category) or not CATEGORY_PATTERN.fullmatch(str(category)):
            errors.append(f"{prefix}.category must use UPPER_SNAKE_CASE")
        if item.get("severity") not in SEVERITIES:
            errors.append(f"{prefix}.severity must be one of {sorted(SEVERITIES)}")
        if is_v1:
            enum_field(item, "disposition", DISPOSITIONS, prefix, errors)
            recommendation = item.get("recommendation")
            if recommendation is not None and not nonempty_string(recommendation):
                errors.append(f"{prefix}.recommendation must be a non-empty string")
            resolution_ids = string_list(item.get("resolution_evidence_ids"), f"{prefix}.resolution_evidence_ids", errors)
            for identifier in resolution_ids:
                if identifier not in evidence_index:
                    errors.append(f"{prefix} references unknown evidence in resolution_evidence_ids: {identifier}")
            if item.get("disposition") == "FIXED" and not resolution_ids:
                warnings.append(f"{prefix} is FIXED without resolution evidence")
        add_required_string_errors(item, ("expected", "actual", "impact"), prefix, errors)
        claim_ids = string_list(item.get("claim_ids"), f"{prefix}.claim_ids", errors)
        evidence_ids = string_list(item.get("evidence_ids"), f"{prefix}.evidence_ids", errors)
        if not claim_ids:
            errors.append(f"{prefix}.claim_ids must contain at least one claim")
        if not evidence_ids:
            errors.append(f"{prefix}.evidence_ids must contain at least one evidence item")
        for identifier in claim_ids:
            if identifier not in claim_index:
                errors.append(f"{prefix} references unknown claim: {identifier}")
        for identifier in evidence_ids:
            if identifier not in evidence_index:
                errors.append(f"{prefix} references unknown evidence: {identifier}")

    for index, item in enumerate(claims):
        prefix = f"claims[{index}]"
        add_required_string_errors(item, ("statement",), prefix, errors)
        if is_v1:
            enum_field(item, "claim_type", CLAIM_TYPES, prefix, errors)
            enum_field(item, "criticality", CRITICALITIES, prefix, errors)
            source_locator = item.get("source_locator")
            if source_locator is not None and not nonempty_string(source_locator):
                errors.append(f"{prefix}.source_locator must be a non-empty string")
        status = item.get("status")
        if status not in CLAIM_STATUSES:
            errors.append(f"{prefix}.status must be one of {sorted(CLAIM_STATUSES)}")
        evidence_ids = string_list(item.get("evidence_ids"), f"{prefix}.evidence_ids", errors)
        finding_ids = string_list(item.get("finding_ids"), f"{prefix}.finding_ids", errors)
        for identifier in evidence_ids:
            if identifier not in evidence_index:
                errors.append(f"{prefix} references unknown evidence: {identifier}")
        for identifier in finding_ids:
            if identifier not in finding_index:
                errors.append(f"{prefix} references unknown finding: {identifier}")
        if status == "VERIFIED":
            linked_types = {evidence_index[item_id].get("type") for item_id in evidence_ids if item_id in evidence_index}
            if "RUNTIME" not in linked_types:
                errors.append(f"{prefix} is VERIFIED without linked RUNTIME evidence")
        if status == "MISMATCH" and not finding_ids:
            errors.append(f"{prefix} is MISMATCH without a linked finding")
        if status in {"CONSISTENT", "VERIFIED", "MISMATCH"} and not evidence_ids:
            errors.append(f"{prefix} status {status} requires evidence")
        if status in {"UNVERIFIABLE", "AMBIGUOUS"} and not finding_ids:
            warnings.append(f"{prefix} status {status} has no explanatory finding")

    # Bidirectional reference: every finding must be cited by at least one claim.
    cited_findings = {
        identifier
        for item in claims
        for identifier in item.get("finding_ids", [])
        if isinstance(identifier, str)
    }
    orphan_findings = sorted(set(finding_index) - cited_findings)
    if orphan_findings:
        errors.append(f"findings not referenced by any claim: {', '.join(orphan_findings)}")

    coverage = data.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        total = coverage.get("total_claims")
        mapped = coverage.get("mapped_claims")
        if not isinstance(total, int) or isinstance(total, bool) or total < 0:
            errors.append("coverage.total_claims must be a non-negative integer")
        elif total != len(claims):
            errors.append("coverage.total_claims does not match claims length")
        expected_mapped = sum(bool(item.get("evidence_ids")) for item in claims)
        if not isinstance(mapped, int) or isinstance(mapped, bool) or mapped < 0:
            errors.append("coverage.mapped_claims must be a non-negative integer")
        elif mapped != expected_mapped:
            errors.append("coverage.mapped_claims does not match claims with evidence")

    if is_v1:
        decision = data.get("release_decision")
        if not isinstance(decision, dict):
            errors.append("release_decision must be an object")
        else:
            status = decision.get("status")
            if status not in RELEASE_STATUSES:
                errors.append(f"release_decision.status must be one of {sorted(RELEASE_STATUSES)}")
            if not nonempty_string(decision.get("rationale")):
                errors.append("release_decision.rationale must be a non-empty string")
            for field in ("blocking_finding_ids", "conditional_finding_ids"):
                ids = string_list(decision.get(field), f"release_decision.{field}", errors)
                for identifier in ids:
                    if identifier not in finding_index:
                        errors.append(f"release_decision.{field} references unknown finding: {identifier}")
            if status == "READY":
                if any(
                    item.get("severity") in {"BLOCKER", "MAJOR"} and item.get("disposition", "OPEN") == "OPEN"
                    for item in findings
                ):
                    errors.append("release_decision is READY despite unresolved BLOCKER or MAJOR findings")
                core_claims = [item for item in claims if item.get("criticality") == "CORE"]
                if any(not item.get("evidence_ids") for item in core_claims):
                    errors.append("release_decision is READY but CORE claims lack evidence")
                if any(item.get("status") in {"MISMATCH", "UNVERIFIABLE"} for item in core_claims):
                    errors.append("release_decision is READY but CORE claims are MISMATCH or UNVERIFIABLE")
        limitations = data.get("limitations")
        if limitations is None or not isinstance(limitations, list):
            errors.append("limitations must be an array")
        else:
            string_list(limitations, "limitations", errors)
    else:
        readiness = data.get("release_readiness")
        if readiness not in RELEASE_STATUSES:
            errors.append(f"release_readiness must be one of {sorted(RELEASE_STATUSES)}")
        if readiness == "READY":
            if any(item.get("severity") in {"BLOCKER", "MAJOR"} for item in findings):
                warnings.append("release_readiness is READY despite BLOCKER or MAJOR findings")
            if any(item.get("status") in {"MISMATCH", "UNVERIFIABLE"} for item in claims):
                warnings.append("release_readiness is READY despite unresolved claims")

    if repo_root is not None:
        root = Path(repo_root)
        if not root.is_dir():
            errors.append(f"--repo-root is not a directory: {root}")
        else:
            resolved_root = root.resolve()
            for index, item in enumerate(evidence):
                prefix = f"evidence[{index}]"
                path_value = item.get("artifact") if item.get("type") == "RUNTIME" else item.get("path")
                if not relative_evidence_path(path_value):
                    continue  # already reported as an unsafe/missing path
                normalized = str(path_value).replace("\\", "/")
                target = root / normalized
                try:
                    resolved = target.resolve()
                except OSError:
                    resolved = None
                if resolved is None or not resolved.is_file() or not resolved.is_relative_to(resolved_root):
                    errors.append(f"{prefix} path does not exist under repository root: {normalized}")

    used_evidence = {
        identifier
        for item in claims + findings
        for identifier in item.get("evidence_ids", [])
        if isinstance(identifier, str)
    }
    unused_evidence = sorted(set(evidence_index) - used_evidence)
    if unused_evidence:
        warnings.append(f"unused evidence IDs: {', '.join(unused_evidence)}")

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Audit summary validation",
        "",
        f"- Valid: `{str(result['valid']).lower()}`",
        f"- Errors: {len(result['errors'])}",
        f"- Warnings: {len(result['warnings'])}",
        "",
        "## Errors",
        "",
    ]
    if result["errors"]:
        lines.extend(f"- {item}" for item in result["errors"])
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    if result["warnings"]:
        lines.extend(f"- {item}" for item in result["warnings"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        result = validate_report(load_json(args.audit_summary), repo_root=args.repo_root)
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
        if not result["valid"]:
            return 2
        return 1 if result["warnings"] else 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
