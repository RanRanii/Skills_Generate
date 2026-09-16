from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from validate_audit_output import markdown_report, validate_report  # noqa: E402


def valid_report() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "audit_id": "AUD-TEST",
        "audit_profile": "STATIC_AUDIT",
        "subject": {
            "manuscript": "manuscript.md",
            "repository": "repository",
            "commit": "working-tree",
        },
        "claims": [
            {
                "claim_id": "CLM-001",
                "claim_type": "METRIC",
                "criticality": "CORE",
                "source_locator": "Table 2, row 1",
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
                "strength": "DIRECT",
                "generated_by": "HUMAN",
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
                "disposition": "OPEN",
                "claim_ids": ["CLM-001"],
                "evidence_ids": ["EVD-001"],
                "expected": "0.001",
                "actual": "0.01",
                "impact": "The public training protocol differs from the manuscript.",
                "recommendation": "Align the launcher with the manuscript.",
                "resolution_evidence_ids": [],
            }
        ],
        "coverage": {"total_claims": 1, "mapped_claims": 1},
        "release_decision": {
            "status": "BLOCKED",
            "blocking_finding_ids": ["FND-001"],
            "conditional_finding_ids": [],
            "rationale": "A core metric claim is MISMATCH.",
        },
        "limitations": ["No dynamic reproduction was run."],
    }


def v03_report() -> dict[str, object]:
    report = valid_report()
    report["schema_version"] = "0.3"
    report["scope"] = report.pop("subject")  # type: ignore[assignment]
    report["release_readiness"] = "BLOCKED"  # type: ignore[assignment]
    for key in ("audit_profile", "release_decision", "limitations"):
        report.pop(key, None)
    return report


class AuditOutputValidationTests(unittest.TestCase):
    def test_valid_report_has_no_errors_or_warnings(self) -> None:
        result = validate_report(valid_report())
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["warnings"], [])

    def test_v03_report_is_accepted_with_deprecation_warning(self) -> None:
        result = validate_report(v03_report())
        self.assertTrue(result["valid"], result)
        self.assertTrue(any("0.3" in item and "deprecated" in item for item in result["warnings"]))

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

    def test_runtime_evidence_requires_structured_fields(self) -> None:
        report = valid_report()
        report["claims"][0]["status"] = "VERIFIED"  # type: ignore[index]
        report["claims"][0]["finding_ids"] = []  # type: ignore[index]
        report["evidence"] = [
            {
                "evidence_id": "EVD-001",
                "type": "RUNTIME",
                "command": "python src/train.py",
                "commit": "abc1234",
                # missing exit_status and artifact
                "observation": "Training reproduced the paper result.",
            }
        ]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("exit_status" in item for item in result["errors"]), result)
        self.assertTrue(any("artifact" in item for item in result["errors"]), result)

    def test_release_decision_ready_with_open_major_is_invalid(self) -> None:
        report = valid_report()
        report["release_decision"]["status"] = "READY"  # type: ignore[index]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("READY despite unresolved" in item for item in result["errors"]))

    def test_repo_root_rejects_missing_evidence_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = validate_report(valid_report(), repo_root=Path(directory))
        self.assertFalse(result["valid"])
        self.assertTrue(any("does not exist under repository root" in item for item in result["errors"]))

    def test_digest_must_be_sha256(self) -> None:
        report = valid_report()
        report["evidence"][0]["digest"] = "not-a-digest"  # type: ignore[index]
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("digest" in item for item in result["errors"]))

    def test_orphan_finding_is_invalid(self) -> None:
        report = valid_report()
        report["findings"].append(  # type: ignore[attr-defined]
            {
                "finding_id": "FND-002",
                "category": "INCOMPLETE_SEEDING",
                "severity": "MINOR",
                "disposition": "OPEN",
                "claim_ids": ["CLM-001"],
                "evidence_ids": ["EVD-001"],
                "expected": "full seeding",
                "actual": "partial seeding",
                "impact": "minor",
                "resolution_evidence_ids": [],
            }
        )
        result = validate_report(report)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not referenced by any claim" in item for item in result["errors"]))

    def test_markdown_uses_none_only_for_empty_sections(self) -> None:
        clean = markdown_report({"valid": True, "errors": [], "warnings": []})
        self.assertEqual(clean.count("- None"), 2)
        failed = markdown_report({"valid": False, "errors": ["bad"], "warnings": []})
        self.assertIn("- bad", failed)
        self.assertEqual(failed.count("- None"), 1)


if __name__ == "__main__":
    unittest.main()
