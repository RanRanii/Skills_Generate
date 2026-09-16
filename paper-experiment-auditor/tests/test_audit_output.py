from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_audit_output import markdown_report, validate_report  # noqa: E402


def valid_report() -> dict[str, object]:
    return {
        "schema_version": "0.3",
        "audit_id": "AUD-TEST",
        "scope": {
            "manuscript": "manuscript.md",
            "repository": "repository",
            "commit": "working-tree",
        },
        "claims": [
            {
                "claim_id": "CLM-001",
                "statement": "The learning rate is 0.001.",
                "status": "MISMATCH",
                "evidence_ids": ["EVD-001"],
                "finding_ids": ["FND-001"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "EVD-001",
                "type": "CONFIG",
                "path": "configs/train.json",
                "locator": "learning_rate",
                "observation": "The effective value is 0.01.",
            }
        ],
        "findings": [
            {
                "finding_id": "FND-001",
                "category": "CONFIG_OVERRIDE",
                "severity": "MAJOR",
                "claim_ids": ["CLM-001"],
                "evidence_ids": ["EVD-001"],
                "expected": "0.001",
                "actual": "0.01",
                "impact": "The public training protocol differs from the manuscript.",
            }
        ],
        "coverage": {"total_claims": 1, "mapped_claims": 1},
        "release_readiness": "BLOCKED",
    }


class AuditOutputValidationTests(unittest.TestCase):
    def test_valid_report_has_no_errors_or_warnings(self) -> None:
        result = validate_report(valid_report())
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["warnings"], [])

    def test_unknown_evidence_reference_is_invalid(self) -> None:
        report = valid_report()
        report["claims"][0]["evidence_ids"] = ["EVD-999"]  # type: ignore[index]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unknown evidence" in item for item in result["errors"]))

    def test_verified_claim_requires_runtime_evidence(self) -> None:
        report = valid_report()
        report["claims"][0]["status"] = "VERIFIED"  # type: ignore[index]
        report["claims"][0]["finding_ids"] = []  # type: ignore[index]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("without linked RUNTIME" in item for item in result["errors"]))

    def test_mismatch_requires_linked_finding(self) -> None:
        report = valid_report()
        report["claims"][0]["finding_ids"] = []  # type: ignore[index]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("without a linked finding" in item for item in result["errors"]))

    def test_absolute_or_parent_evidence_paths_are_rejected(self) -> None:
        for unsafe in ("C:/private/train.py", "/private/train.py", "../train.py"):
            with self.subTest(path=unsafe):
                report = copy.deepcopy(valid_report())
                report["evidence"][0]["path"] = unsafe  # type: ignore[index]
                result = validate_report(report)
                self.assertFalse(result["valid"])
                self.assertTrue(any("safe relative path" in item for item in result["errors"]))

    def test_coverage_must_match_claims(self) -> None:
        report = valid_report()
        report["coverage"] = {"total_claims": 2, "mapped_claims": 0}
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertGreaterEqual(sum("coverage." in item for item in result["errors"]), 2)

    def test_markdown_uses_none_only_for_empty_sections(self) -> None:
        clean = markdown_report({"valid": True, "errors": [], "warnings": []})
        self.assertEqual(clean.count("- None"), 2)
        failed = markdown_report({"valid": False, "errors": ["bad"], "warnings": []})
        self.assertIn("- bad", failed)
        self.assertEqual(failed.count("- None"), 1)


if __name__ == "__main__":
    unittest.main()
