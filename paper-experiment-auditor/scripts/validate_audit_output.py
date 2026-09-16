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
RELEASE_READINESS = {"READY", "CONDITIONAL", "BLOCKED", "UNKNOWN"}
ID_PATTERNS = {
    "claim_id": re.compile(r"^CLM-\d{3,}$"),
    "evidence_id": re.compile(r"^EVD-\d{3,}$"),
    "finding_id": re.compile(r"^FND-\d{3,}$"),
}
CATEGORY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
WINDOWS_ABSOLUTE = re.compile(r"^[A-Za-z]:[\\/]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audit_summary", type=Path, help="audit-summary.json to validate")
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


def validate_report(data: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(data, dict):
        return {"valid": False, "errors": ["audit summary must be a JSON object"], "warnings": []}

    if str(data.get("schema_version")) != "0.3":
        errors.append("schema_version must be '0.3'")
    if not nonempty_string(data.get("audit_id")):
        errors.append("audit_id must be a non-empty string")

    scope = data.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
    else:
        add_required_string_errors(scope, ("manuscript", "repository", "commit"), "scope", errors)

    claims, claim_index = validate_ids(data.get("claims"), "claim_id", "claims", errors)
    evidence, evidence_index = validate_ids(data.get("evidence"), "evidence_id", "evidence", errors)
    findings, finding_index = validate_ids(data.get("findings"), "finding_id", "findings", errors)

    for index, item in enumerate(evidence):
        prefix = f"evidence[{index}]"
        evidence_type = item.get("type")
        if evidence_type not in EVIDENCE_TYPES:
            errors.append(f"{prefix}.type must be one of {sorted(EVIDENCE_TYPES)}")
        add_required_string_errors(item, ("path", "locator", "observation"), prefix, errors)
        if item.get("path") is not None and not relative_evidence_path(item.get("path")):
            errors.append(f"{prefix}.path must be a safe relative path")

    for index, item in enumerate(findings):
        prefix = f"findings[{index}]"
        category = item.get("category")
        if not nonempty_string(category) or not CATEGORY_PATTERN.fullmatch(str(category)):
            errors.append(f"{prefix}.category must use UPPER_SNAKE_CASE")
        if item.get("severity") not in SEVERITIES:
            errors.append(f"{prefix}.severity must be one of {sorted(SEVERITIES)}")
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

    readiness = data.get("release_readiness")
    if readiness not in RELEASE_READINESS:
        errors.append(f"release_readiness must be one of {sorted(RELEASE_READINESS)}")
    if readiness == "READY":
        if any(item.get("severity") in {"BLOCKER", "MAJOR"} for item in findings):
            warnings.append("release_readiness is READY despite BLOCKER or MAJOR findings")
        if any(item.get("status") in {"MISMATCH", "UNVERIFIABLE"} for item in claims):
            warnings.append("release_readiness is READY despite unresolved claims")

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
        result = validate_report(load_json(args.audit_summary))
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
