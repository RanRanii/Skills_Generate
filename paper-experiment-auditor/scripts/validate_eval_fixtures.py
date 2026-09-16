#!/usr/bin/env python3
"""Validate behavioral evaluation fixtures for paper-experiment-auditor."""

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
READINESS = {"READY", "CONDITIONAL", "BLOCKED", "UNKNOWN"}
CATEGORY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
CASE_ID_PATTERN = re.compile(r"^\d{2}-[a-z0-9-]+$")
SENSITIVE_NAMES = {".env", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"}
MAX_FIXTURE_BYTES = 1_000_000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases_root", type=Path, help="Directory containing evaluation case folders")
    parser.add_argument("--output", type=Path, help="Write JSON validation report to this file")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    return not path.is_absolute() and ".." not in path.parts and not re.match(r"^[A-Za-z]:/", normalized)


def string_list(value: Any, label: str, allowed: set[str] | None, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        errors.append(f"{label} must be an array of non-empty strings")
        return []
    values = [str(item) for item in value]
    if len(values) != len(set(values)):
        errors.append(f"{label} contains duplicate values")
    if allowed is not None:
        invalid = sorted(set(values) - allowed)
        if invalid:
            errors.append(f"{label} contains invalid values: {', '.join(invalid)}")
    return values


def validate_required_finding(item: Any, label: str, case_dir: Path, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"{label} must be an object")
        return
    category = item.get("category")
    if not isinstance(category, str) or not CATEGORY_PATTERN.fullmatch(category):
        errors.append(f"{label}.category must use UPPER_SNAKE_CASE")
    string_list(item.get("allowed_claim_statuses"), f"{label}.allowed_claim_statuses", CLAIM_STATUSES, errors)
    string_list(item.get("allowed_severities"), f"{label}.allowed_severities", SEVERITIES, errors)
    string_list(item.get("required_evidence_types"), f"{label}.required_evidence_types", EVIDENCE_TYPES, errors)
    fixture_paths = string_list(item.get("fixture_paths"), f"{label}.fixture_paths", None, errors)
    for relative in fixture_paths:
        if not safe_relative(relative):
            errors.append(f"{label}.fixture_paths contains unsafe path: {relative}")
        elif not (case_dir / relative).is_file():
            errors.append(f"{label}.fixture_paths does not exist: {relative}")
    if not isinstance(item.get("blocking"), bool):
        errors.append(f"{label}.blocking must be boolean")


def validate_case(case_dir: Path) -> tuple[str | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    manifest_path = case_dir / "case.json"
    oracle_path = case_dir / "oracle.json"
    try:
        manifest = load_json(manifest_path)
        oracle = load_json(oracle_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, [str(exc)], warnings

    case_id: str | None = None
    if not isinstance(manifest, dict):
        errors.append("case.json must contain an object")
    else:
        case_id_value = manifest.get("case_id")
        if not isinstance(case_id_value, str) or not CASE_ID_PATTERN.fullmatch(case_id_value):
            errors.append("case.json.case_id has invalid format")
        else:
            case_id = case_id_value
            if case_id != case_dir.name:
                errors.append("case.json.case_id must match the directory name")
        for field in ("title", "description"):
            if not isinstance(manifest.get(field), str) or not manifest[field].strip():
                errors.append(f"case.json.{field} must be a non-empty string")
        category = manifest.get("category")
        if not isinstance(category, str) or not CATEGORY_PATTERN.fullmatch(category):
            errors.append("case.json.category must use UPPER_SNAKE_CASE")

    for name in ("request.md", "manuscript.md"):
        path = case_dir / name
        if not path.is_file() or not path.read_text(encoding="utf-8-sig").strip():
            errors.append(f"missing or empty required file: {name}")
    repository = case_dir / "repository"
    if not repository.is_dir() or not any(path.is_file() for path in repository.rglob("*")):
        errors.append("repository must contain at least one file")

    if not isinstance(oracle, dict):
        errors.append("oracle.json must contain an object")
    else:
        required = oracle.get("required_findings")
        if not isinstance(required, list):
            errors.append("oracle.required_findings must be an array")
            required = []
        categories: list[str] = []
        for index, item in enumerate(required):
            validate_required_finding(item, f"oracle.required_findings[{index}]", case_dir, errors)
            if isinstance(item, dict) and isinstance(item.get("category"), str):
                categories.append(item["category"])
        if len(categories) != len(set(categories)):
            errors.append("oracle.required_findings categories must be unique")
        forbidden_categories = string_list(
            oracle.get("forbidden_categories"),
            "oracle.forbidden_categories",
            None,
            errors,
        )
        for category in forbidden_categories:
            if not CATEGORY_PATTERN.fullmatch(category):
                errors.append(f"oracle.forbidden_categories has invalid category: {category}")
        overlap = sorted(set(categories) & set(forbidden_categories))
        if overlap:
            errors.append(f"required and forbidden categories overlap: {', '.join(overlap)}")
        string_list(oracle.get("forbidden_severities"), "oracle.forbidden_severities", SEVERITIES, errors)
        string_list(oracle.get("expected_release_readiness"), "oracle.expected_release_readiness", READINESS, errors)
        maximum = oracle.get("max_high_severity_false_positives")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
            errors.append("oracle.max_high_severity_false_positives must be a non-negative integer")

    for path in case_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size > MAX_FIXTURE_BYTES:
            errors.append(f"fixture file exceeds {MAX_FIXTURE_BYTES} bytes: {path.relative_to(case_dir).as_posix()}")
        if path.name.lower() in SENSITIVE_NAMES or path.suffix.lower() in {".pem", ".key"}:
            errors.append(f"sensitive-looking fixture filename: {path.relative_to(case_dir).as_posix()}")

    if not errors and not oracle.get("required_findings"):
        warnings.append("control case has no required findings; false-positive constraints remain active")
    return case_id, errors, warnings


def validate_cases(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise ValueError(f"cases root is not a directory: {root}")
    case_dirs = sorted(path for path in root.iterdir() if path.is_dir())
    if not case_dirs:
        raise ValueError("cases root contains no case directories")
    case_results: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    global_errors: list[str] = []
    for case_dir in case_dirs:
        case_id, errors, warnings = validate_case(case_dir)
        if case_id:
            if case_id in seen_ids:
                errors.append(f"duplicate case_id across fixtures: {case_id}")
            seen_ids.add(case_id)
        case_results.append(
            {
                "directory": case_dir.name,
                "case_id": case_id,
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
            }
        )
    return {
        "valid": not global_errors and all(item["valid"] for item in case_results),
        "case_count": len(case_results),
        "errors": global_errors,
        "cases": case_results,
    }


def main() -> int:
    args = parse_args()
    try:
        result = validate_cases(args.cases_root)
        rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        return 0 if result["valid"] else 2
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
