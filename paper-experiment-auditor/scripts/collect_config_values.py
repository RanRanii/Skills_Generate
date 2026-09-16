#!/usr/bin/env python3
"""Flatten JSON, TOML, INI, and optionally YAML experiment configurations."""

from __future__ import annotations

import argparse
import configparser
import csv
import io
import json
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
    tomllib = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Configuration files to collect")
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--output", type=Path, help="Write output to this file instead of stdout")
    return parser.parse_args()


def load_config(path: Path) -> Any:
    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if suffix == ".toml":
        if tomllib is None:
            raise ValueError("TOML requires Python 3.11 or newer")
        with path.open("rb") as handle:
            return tomllib.load(handle)
    if suffix in {".ini", ".cfg"}:
        parser = configparser.ConfigParser(interpolation=None)
        with path.open("r", encoding="utf-8-sig") as handle:
            parser.read_file(handle)
        return {section: dict(parser.items(section)) for section in parser.sections()}
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError("YAML input requires PyYAML; install it or export JSON/TOML") from exc
        with path.open("r", encoding="utf-8-sig") as handle:
            return yaml.safe_load(handle)
    raise ValueError(f"unsupported configuration format: {path}")


def flatten(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(value, dict):
        output: list[tuple[str, Any]] = []
        for key in sorted(value, key=lambda item: str(item)):
            child = f"{prefix}.{key}" if prefix else str(key)
            output.extend(flatten(value[key], child))
        return output
    if isinstance(value, list):
        output = []
        for index, item in enumerate(value):
            child = f"{prefix}[{index}]" if prefix else f"[{index}]"
            output.extend(flatten(item, child))
        return output
    return [(prefix or "<root>", value)]


def is_sensitive_key(key: str) -> bool:
    expanded = []
    for character in key:
        if character.isupper() and expanded and expanded[-1].isalnum():
            expanded.append("_")
        expanded.append(character.lower())
    segments = [segment for segment in "".join(expanded).replace("-", ".").replace("_", ".").split(".") if segment]
    if any(segment in {"password", "passwd", "secret", "token"} for segment in segments):
        return True
    pairs = set(zip(segments, segments[1:]))
    return bool(pairs & {("api", "key"), ("access", "key"), ("private", "key")})


def safe_value(key: str, value: Any) -> Any:
    if is_sensitive_key(key):
        return "<REDACTED>"
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def display_source(path: Path) -> str:
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.name


def collect(paths: list[Path]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            raise ValueError(f"configuration file does not exist: {path}")
        data = load_config(path)
        for key, value in flatten(data):
            rendered = safe_value(key, value)
            records.append(
                {
                    "source": display_source(path),
                    "key": key,
                    "value": rendered,
                    "value_type": "redacted" if rendered == "<REDACTED>" else type(value).__name__,
                }
            )
    return {"schema_version": "1.0", "records": sorted(records, key=lambda row: (row["source"], row["key"]))}


def render_csv(report: dict[str, Any]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=("source", "key", "value", "value_type"), lineterminator="\n")
    writer.writeheader()
    writer.writerows(report["records"])
    return stream.getvalue()


def main() -> int:
    args = parse_args()
    try:
        report = collect(args.files)
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
            if args.format == "json"
            else render_csv(report)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        return 0
    except (OSError, ValueError, json.JSONDecodeError, configparser.Error) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
