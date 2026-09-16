#!/usr/bin/env python3
"""Collect a deterministic, content-free inventory of a research repository."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
}

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

CATEGORY_SUFFIXES = {
    "source": {".py", ".r", ".jl", ".m", ".cpp", ".cc", ".c", ".h", ".hpp", ".java"},
    "config": {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg"},
    "notebook": {".ipynb", ".qmd", ".rmd"},
    "documentation": {".md", ".rst", ".txt"},
    "tabular-result": {".csv", ".tsv", ".parquet", ".xlsx", ".xls"},
    "figure": {".png", ".jpg", ".jpeg", ".svg", ".pdf", ".tif", ".tiff"},
    "model-artifact": {".pt", ".pth", ".ckpt", ".onnx", ".safetensors"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repository root to inspect")
    parser.add_argument("--max-depth", type=int, default=8, help="Maximum directory depth")
    parser.add_argument("--exclude", action="append", default=[], help="Additional glob to exclude")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write output to this file instead of stdout")
    return parser.parse_args()


def category_for(path: Path) -> str:
    suffix = path.suffix.lower()
    for category, suffixes in CATEGORY_SUFFIXES.items():
        if suffix in suffixes:
            return category
    if path.name.lower() in {"dockerfile", "makefile", "environment.yml", "requirements.txt"}:
        return "environment"
    return "other"


def matches_any(path: str, patterns: list[str] | tuple[str, ...]) -> bool:
    name = Path(path).name
    return any(fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(name, pattern) for pattern in patterns)


def collect(root: Path, max_depth: int, excludes: list[str]) -> dict[str, Any]:
    if max_depth < 0:
        raise ValueError("--max-depth must be zero or greater")
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root is not a directory: {root}")

    files: list[dict[str, Any]] = []
    warnings: list[dict[str, str]] = []
    category_counts: Counter[str] = Counter()
    suffix_counts: Counter[str] = Counter()
    total_bytes = 0

    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        relative_dir = current_path.relative_to(root)
        depth = 0 if relative_dir == Path(".") else len(relative_dir.parts)

        kept_dirs = []
        for dirname in sorted(dirnames):
            relative = (relative_dir / dirname).as_posix()
            if dirname in DEFAULT_EXCLUDED_DIRS or matches_any(relative, excludes):
                continue
            if depth < max_depth:
                kept_dirs.append(dirname)
        dirnames[:] = kept_dirs

        for filename in sorted(filenames):
            path = current_path / filename
            relative = path.relative_to(root).as_posix()
            if matches_any(relative, excludes):
                continue
            try:
                stat = path.lstat()
            except OSError as exc:
                warnings.append({"path": relative, "warning": f"stat failed: {exc}"})
                continue

            category = category_for(path)
            suffix = path.suffix.lower() or "<none>"
            entry = {
                "path": relative,
                "kind": "symlink" if path.is_symlink() else "file",
                "size_bytes": stat.st_size,
                "category": category,
            }
            files.append(entry)
            category_counts[category] += 1
            suffix_counts[suffix] += 1
            total_bytes += stat.st_size

            if matches_any(relative.lower(), SENSITIVE_PATTERNS):
                warnings.append({"path": relative, "warning": "sensitive filename; review before publishing"})

    return {
        "schema_version": "1.0",
        "root": ".",
        "summary": {
            "file_count": len(files),
            "total_bytes": total_bytes,
            "categories": dict(sorted(category_counts.items())),
            "suffixes": dict(sorted(suffix_counts.items())),
        },
        "warnings": sorted(warnings, key=lambda item: (item["path"], item["warning"])),
        "files": sorted(files, key=lambda item: item["path"]),
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Repository inventory",
        "",
        f"- Files: {summary['file_count']}",
        f"- Total bytes: {summary['total_bytes']}",
        "",
        "## Categories",
        "",
        "| Category | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {key} | {value} |" for key, value in summary["categories"].items())
    lines.extend(["", "## Publishing warnings", ""])
    if report["warnings"]:
        lines.extend(f"- `{item['path']}`: {item['warning']}" for item in report["warnings"])
    else:
        lines.append("- None detected by filename rules.")
    lines.extend(["", "## Files", "", "| Path | Category | Bytes |", "|---|---|---:|"])
    for item in report["files"]:
        safe_path = item["path"].replace("|", "\\|")
        lines.append(f"| `{safe_path}` | {item['category']} | {item['size_bytes']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        report = collect(Path(args.root), args.max_depth, args.exclude)
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
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
