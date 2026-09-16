#!/usr/bin/env python3
"""Deterministically check a target repository's release manifest.

Validates that every declared public entry point, configuration file, result
asset and checkpoint exists as a safe relative path inside the repository. It
never executes the target repository's code and does not replace a full secret
scan or security audit.
"""

from __future__ import annotations

import argparse
import configparser
import fnmatch
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

try:
    import tomllib  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Python < 3.11
    tomllib = None  # type: ignore[assignment]


SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "id_rsa",
    "id_ed25519",
    "credentials.*",
    "secrets.*",
)
LOCAL_PATH_HINTS = (
    "C:/",
    "D:/",
    "/home/",
    "/Users/",
    "/tmp/",
    "~",
    "\\",
    "private",
    "internal",
)
CONFIG_SUFFIXES = {".json", ".toml", ".ini", ".cfg"}

ENTRY_FIELDS = ("data_preparation", "training", "evaluation", "result_generation")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, help="release-manifest.json to check")
    parser.add_argument("--repo-root", type=Path, help="Repository root (defaults to manifest directory)")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write report to this file instead of stdout")
    return parser.parse_args()


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise ValueError(f"manifest does not exist: {path}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_relative(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    normalized = value.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("//"):
        return False
    if len(normalized) >= 2 and normalized[1] == ":":
        return False
    return ".." not in PurePosixPath(normalized).parts


def matches_any(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(name.lower(), pattern.lower()) for pattern in patterns)


def parse_config(path: Path) -> str | None:
    """Return a parse error message, or None when the config parses cleanly."""
    suffix = path.suffix.lower()
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        return f"cannot read: {exc}"
    if suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            return f"invalid JSON: {exc}"
    elif suffix == ".toml":
        if tomllib is None:
            return None  # unavailable; skip rather than fail
        try:
            tomllib.loads(text)
        except Exception as exc:  # tomllib.TOMLDecodeError
            return f"invalid TOML: {exc}"
    elif suffix in {".ini", ".cfg"}:
        parser = configparser.ConfigParser()
        try:
            parser.read_string(text)
        except (configparser.Error, UnicodeDecodeError) as exc:
            return f"invalid INI/CFG: {exc}"
    return None


def find_symlink_escape(repo_root: Path, relative: str) -> bool:
    path = repo_root / relative
    if not path.is_symlink():
        return False
    try:
        resolved = path.resolve()
    except OSError:
        return True
    return not resolved.is_relative_to(repo_root.resolve())


def collect_declared_paths(manifest: dict[str, Any], repo_root: Path, errors: list[str]) -> list[tuple[str, str, bool]]:
    """Return (field, path, config_check) triples; config_check True for default_configs."""
    declared: list[tuple[str, str, bool]] = []
    if not isinstance(manifest.get("documentation"), list):
        errors.append("documentation must be an array")
    else:
        declared.extend(("documentation", item, False) for item in manifest["documentation"])

    install = manifest.get("install")
    if not isinstance(install, dict):
        errors.append("install must be an object")
    else:
        env_files = install.get("environment_files")
        if not isinstance(env_files, list):
            errors.append("install.environment_files must be an array")
        else:
            declared.extend(("install.environment_files", item, False) for item in env_files)

    for field in ENTRY_FIELDS:
        entry = manifest.get(field)
        if not isinstance(entry, dict):
            errors.append(f"{field} must be an object")
            continue
        declared.append((f"{field}.entry", entry.get("entry"), False))

    configs = manifest.get("default_configs")
    if not isinstance(configs, list):
        errors.append("default_configs must be an array")
    else:
        declared.extend(("default_configs", item, True) for item in configs)

    checkpoints = manifest.get("checkpoints")
    if not isinstance(checkpoints, dict):
        errors.append("checkpoints must be an object")
    else:
        paths = checkpoints.get("paths")
        if not isinstance(paths, list):
            errors.append("checkpoints.paths must be an array")
        else:
            declared.extend(("checkpoints.paths", item, False) for item in paths)

    outputs = manifest.get("expected_outputs")
    if not isinstance(outputs, list):
        errors.append("expected_outputs must be an array")
    else:
        declared.extend(("expected_outputs", item, False) for item in outputs)

    return declared


def check_manifest(manifest: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    errors: list[str] = []
    findings: list[dict[str, str]] = []
    checks: list[dict[str, Any]] = []

    if not isinstance(manifest, dict):
        return {"valid": False, "errors": ["manifest must be a JSON object"]}
    if str(manifest.get("schema_version")) != "1.0":
        errors.append("schema_version must be '1.0'")

    if not repo_root.is_dir():
        return {"valid": False, "errors": [f"repository root is not a directory: {repo_root}"]}

    for field, path, is_config in collect_declared_paths(manifest, repo_root, errors):
        if not safe_relative(path):
            findings.append({"category": "UNSAFE_PATH", "field": field, "path": str(path), "message": "not a safe relative path"})
            checks.append({"field": field, "path": path, "status": "unsafe"})
            continue
        normalized = str(path).replace("\\", "/")
        if matches_any(Path(normalized).name, SENSITIVE_PATTERNS):
            findings.append({"category": "SENSITIVE_CONTENT_RISK", "field": field, "path": normalized, "message": "sensitive filename"})
        if matches_any(normalized, LOCAL_PATH_HINTS):
            findings.append({"category": "PRIVATE_DEPENDENCY", "field": field, "path": normalized, "message": "local or private path hint"})

        target = repo_root / normalized
        if not target.is_file():
            findings.append({"category": "MISSING_RELEASE_ASSET", "field": field, "path": normalized, "message": "declared path does not exist"})
            checks.append({"field": field, "path": normalized, "status": "missing"})
            continue
        if find_symlink_escape(repo_root, normalized):
            findings.append({"category": "UNSAFE_PATH", "field": field, "path": normalized, "message": "symlink resolves outside repository"})
            checks.append({"field": field, "path": normalized, "status": "external-symlink"})
            continue
        checks.append({"field": field, "path": normalized, "status": "ok"})

        if is_config and target.suffix.lower() in CONFIG_SUFFIXES:
            parse_error = parse_config(target)
            if parse_error:
                findings.append({"category": "INVALID_CONFIG", "field": field, "path": normalized, "message": parse_error})

    return {
        "schema_version": "1.0",
        "valid": not errors,
        "status": "PASS" if (not errors and not findings) else "FAIL",
        "errors": errors,
        "repo_root": str(repo_root),
        "checks": checks,
        "findings": findings,
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# Release package check",
        "",
        f"- Status: `{report['status']}`",
        f"- Repo root: `{report['repo_root']}`",
        f"- Checks: {len(report['checks'])}",
        f"- Findings: {len(report['findings'])}",
        "",
        "## Findings",
        "",
    ]
    if report["findings"]:
        lines.extend(f"- `{item['path']}` ({item['category']}): {item['message']}" for item in report["findings"])
    else:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        manifest = load_json(args.manifest)
        repo_root = (args.repo_root or args.manifest.parent).resolve()
        report = check_manifest(manifest, repo_root)
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2) + "\n"
            if args.format == "json"
            else markdown_report(report)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        if not report["valid"]:
            return 2
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
