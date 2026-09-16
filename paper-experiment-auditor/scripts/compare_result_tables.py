#!/usr/bin/env python3
"""Compare expected and actual scientific result tables with explicit tolerances."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("expected", type=Path, help="Expected CSV, TSV, or JSON table")
    parser.add_argument("actual", type=Path, help="Actual CSV, TSV, or JSON table")
    parser.add_argument("--keys", required=True, help="Comma-separated columns identifying a row")
    parser.add_argument("--metrics", help="Comma-separated columns to compare; default: all expected non-key columns")
    parser.add_argument("--abs-tol", default="0", help="Absolute numeric tolerance")
    parser.add_argument("--rel-tol", default="0", help="Relative numeric tolerance")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="Write report to this file instead of stdout")
    return parser.parse_args()


def read_table(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"table does not exist: {path}")
    suffix = path.suffix.lower()
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
            raise ValueError(f"JSON table must be an array of objects: {path}")
        return [{str(key): value for key, value in row.items()} for row in data]
    if suffix in {".csv", ".tsv"}:
        delimiter = "\t" if suffix == ".tsv" else ","
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter=delimiter)]
    raise ValueError(f"unsupported table format: {path}")


def split_columns(value: str | None) -> list[str]:
    if not value:
        return []
    columns = [item.strip() for item in value.split(",") if item.strip()]
    if len(columns) != len(set(columns)):
        raise ValueError("column lists must not contain duplicates")
    return columns


def columns_for(rows: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for row in rows:
        result.update(row)
    return result


def index_rows(rows: list[dict[str, Any]], keys: list[str], label: str) -> dict[tuple[str, ...], dict[str, Any]]:
    indexed: dict[tuple[str, ...], dict[str, Any]] = {}
    for number, row in enumerate(rows, start=2):
        missing = [key for key in keys if key not in row]
        if missing:
            raise ValueError(f"{label} row {number} is missing key columns: {', '.join(missing)}")
        row_key = tuple(str(row[key]) for key in keys)
        if row_key in indexed:
            raise ValueError(f"{label} contains duplicate key: {row_key}")
        indexed[row_key] = row
    return indexed


def as_decimal(value: Any) -> Decimal | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        text = str(value).strip()
        if not text:
            return None
        number = Decimal(text)
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def compare_value(expected: Any, actual: Any, abs_tol: Decimal, rel_tol: Decimal) -> dict[str, Any]:
    expected_number = as_decimal(expected)
    actual_number = as_decimal(actual)
    if expected_number is not None and actual_number is not None:
        difference = abs(actual_number - expected_number)
        scale = max(abs(expected_number), abs(actual_number))
        threshold = abs_tol + rel_tol * scale
        return {
            "match": difference <= threshold,
            "comparison": "numeric",
            "difference": str(difference),
            "allowed": str(threshold),
        }
    return {
        "match": str(expected) == str(actual),
        "comparison": "exact",
        "difference": None,
        "allowed": None,
    }


def compare(
    expected_rows: list[dict[str, Any]],
    actual_rows: list[dict[str, Any]],
    keys: list[str],
    metrics: list[str],
    abs_tol: Decimal,
    rel_tol: Decimal,
) -> dict[str, Any]:
    if not expected_rows or not actual_rows:
        raise ValueError("both tables must contain at least one data row")
    expected_columns = columns_for(expected_rows)
    actual_columns = columns_for(actual_rows)
    for key in keys:
        if key not in expected_columns or key not in actual_columns:
            raise ValueError(f"key column is not present in both tables: {key}")
    if not metrics:
        metrics = sorted(expected_columns - set(keys))
    if not metrics:
        raise ValueError("no metric columns were selected")
    for metric in metrics:
        if metric not in expected_columns or metric not in actual_columns:
            raise ValueError(f"metric column is not present in both tables: {metric}")

    expected_index = index_rows(expected_rows, keys, "expected table")
    actual_index = index_rows(actual_rows, keys, "actual table")
    expected_keys = set(expected_index)
    actual_keys = set(actual_index)
    differences: list[dict[str, Any]] = []

    for row_key in sorted(expected_keys - actual_keys):
        differences.append({"kind": "missing-row", "key": dict(zip(keys, row_key))})
    for row_key in sorted(actual_keys - expected_keys):
        differences.append({"kind": "extra-row", "key": dict(zip(keys, row_key))})
    for row_key in sorted(expected_keys & actual_keys):
        expected_row = expected_index[row_key]
        actual_row = actual_index[row_key]
        for metric in metrics:
            result = compare_value(expected_row.get(metric), actual_row.get(metric), abs_tol, rel_tol)
            if not result["match"]:
                differences.append(
                    {
                        "kind": "value-mismatch",
                        "key": dict(zip(keys, row_key)),
                        "metric": metric,
                        "expected": expected_row.get(metric),
                        "actual": actual_row.get(metric),
                        "comparison": result["comparison"],
                        "difference": result["difference"],
                        "allowed": result["allowed"],
                    }
                )

    return {
        "schema_version": "1.0",
        "status": "MATCH" if not differences else "MISMATCH",
        "keys": keys,
        "metrics": metrics,
        "absolute_tolerance": str(abs_tol),
        "relative_tolerance": str(rel_tol),
        "summary": {
            "expected_rows": len(expected_rows),
            "actual_rows": len(actual_rows),
            "difference_count": len(differences),
        },
        "differences": differences,
    }


def markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Result comparison",
        "",
        f"- Status: `{report['status']}`",
        f"- Expected rows: {summary['expected_rows']}",
        f"- Actual rows: {summary['actual_rows']}",
        f"- Differences: {summary['difference_count']}",
        f"- Absolute tolerance: {report['absolute_tolerance']}",
        f"- Relative tolerance: {report['relative_tolerance']}",
        "",
        "## Differences",
        "",
    ]
    if not report["differences"]:
        lines.append("No differences found under the configured tolerances.")
    else:
        lines.extend(["| Kind | Key | Metric | Expected | Actual | Difference | Allowed |", "|---|---|---|---|---|---|---|"])
        for item in report["differences"]:
            key = ", ".join(f"{name}={value}" for name, value in item["key"].items())
            lines.append(
                "| {kind} | `{key}` | {metric} | {expected} | {actual} | {difference} | {allowed} |".format(
                    kind=item["kind"],
                    key=key.replace("|", "\\|"),
                    metric=item.get("metric", ""),
                    expected=item.get("expected", ""),
                    actual=item.get("actual", ""),
                    difference=item.get("difference", ""),
                    allowed=item.get("allowed", ""),
                )
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    try:
        keys = split_columns(args.keys)
        if not keys:
            raise ValueError("--keys must contain at least one column")
        metrics = split_columns(args.metrics)
        abs_tol = Decimal(args.abs_tol)
        rel_tol = Decimal(args.rel_tol)
        if abs_tol < 0 or rel_tol < 0:
            raise ValueError("tolerances must be zero or greater")
        report = compare(
            read_table(args.expected),
            read_table(args.actual),
            keys,
            metrics,
            abs_tol,
            rel_tol,
        )
        rendered = (
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
            if args.format == "json"
            else markdown_report(report)
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(rendered)
        return 0 if report["status"] == "MATCH" else 1
    except (OSError, ValueError, InvalidOperation, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
