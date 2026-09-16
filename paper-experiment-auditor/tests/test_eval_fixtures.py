from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
CASES = SKILL_ROOT / "evals" / "cases"


def run_script(name: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(arg) for arg in args)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def config_override_report() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "audit_id": "AUD-EVAL-02",
        "audit_profile": "STATIC_AUDIT",
        "subject": {
            "manuscript": "manuscript.md",
            "repository": "repository",
            "commit": "fixture",
        },
        "claims": [
            {
                "claim_id": "CLM-001",
                "claim_type": "TRAINING",
                "criticality": "CORE",
                "source_locator": "Section 3.1",
                "statement": "Training uses a learning rate of 0.001.",
                "status": "MISMATCH",
                "evidence_ids": ["EVD-001", "EVD-002"],
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
                "observation": "The file declares 0.001.",
            },
            {
                "evidence_id": "EVD-002",
                "type": "CODE",
                "strength": "DIRECT",
                "generated_by": "HUMAN",
                "path": "src/run.py",
                "locator": "effective_config",
                "observation": "The launcher replaces the value with 0.01.",
            },
        ],
        "findings": [
            {
                "finding_id": "FND-001",
                "category": "CONFIG_OVERRIDE",
                "severity": "MAJOR",
                "disposition": "OPEN",
                "claim_ids": ["CLM-001"],
                "evidence_ids": ["EVD-001", "EVD-002"],
                "expected": "0.001",
                "actual": "0.01",
                "impact": "The effective protocol differs from the paper.",
                "recommendation": "Align the launcher with the manuscript.",
                "resolution_evidence_ids": [],
            }
        ],
        "coverage": {"total_claims": 1, "mapped_claims": 1},
        "release_decision": {
            "status": "BLOCKED",
            "blocking_finding_ids": ["FND-001"],
            "conditional_finding_ids": [],
            "rationale": "Effective training config conflicts with the manuscript.",
        },
        "limitations": ["No dynamic reproduction was run."],
    }


class EvaluationFixtureTests(unittest.TestCase):
    def test_all_nine_fixtures_are_valid(self) -> None:
        completed = run_script("validate_eval_fixtures.py", CASES)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertTrue(result["valid"])
        self.assertEqual(result["case_count"], 9)

    def test_reference_audit_passes_config_override_case(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit-summary.json"
            audit.write_text(json.dumps(config_override_report()), encoding="utf-8")
            completed = run_script("grade_audit_case.py", CASES / "02-config-override", audit)
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["score"], 100)

    def test_hallucinated_evidence_path_blocks_case(self) -> None:
        report = copy.deepcopy(config_override_report())
        report["evidence"][1]["path"] = "src/missing.py"  # type: ignore[index]
        with tempfile.TemporaryDirectory() as directory:
            audit = Path(directory) / "audit-summary.json"
            audit.write_text(json.dumps(report), encoding="utf-8")
            completed = run_script("grade_audit_case.py", CASES / "02-config-override", audit)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("EVD-002", result["hallucinated_evidence"])


if __name__ == "__main__":
    unittest.main()
