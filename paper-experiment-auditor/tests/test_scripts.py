from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"


def run_script(name: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(arg) for arg in args)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class RepositoryInventoryTests(unittest.TestCase):
    def test_inventory_is_sorted_and_warns_about_sensitive_filenames(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "src").mkdir()
            (root / ".git").mkdir()
            (root / "src" / "train.py").write_text("print('ok')\n", encoding="utf-8")
            (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            (root / ".git" / "config").write_text("ignored\n", encoding="utf-8")

            completed = run_script("collect_repo_structure.py", root)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            paths = [item["path"] for item in report["files"]]
            self.assertEqual(paths, sorted(paths))
            self.assertIn("src/train.py", paths)
            self.assertNotIn(".git/config", paths)
            self.assertTrue(any(item["path"] == ".env" for item in report["warnings"]))


class ConfigCollectorTests(unittest.TestCase):
    def test_json_is_flattened_and_secrets_are_redacted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "train.json"
            json_path.write_text(
                json.dumps(
                    {
                        "training": {"lr": 0.001},
                        "api_token": "do-not-print",
                        "accessKey": "also-do-not-print",
                    }
                ),
                encoding="utf-8",
            )

            completed = run_script("collect_config_values.py", json_path)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            records = {(row["source"], row["key"]): row for row in report["records"]}
            self.assertEqual(records[(json_path.name, "api_token")]["value"], "<REDACTED>")
            self.assertEqual(records[(json_path.name, "accessKey")]["value"], "<REDACTED>")
            self.assertEqual(records[(json_path.name, "training.lr")]["value"], 0.001)

    @unittest.skipIf(sys.version_info < (3, 11), "TOML uses the Python 3.11+ standard library")
    def test_toml_is_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            toml_path = root / "model.toml"
            toml_path.write_text("[model]\nhidden_size = 128\n", encoding="utf-8")

            completed = run_script("collect_config_values.py", toml_path)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            records = {(row["source"], row["key"]): row for row in report["records"]}
            self.assertEqual(records[(toml_path.name, "model.hidden_size")]["value"], 128)


class ResultComparisonTests(unittest.TestCase):
    def test_numeric_tolerance_and_mismatch_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.csv"
            actual = root / "actual.csv"
            expected.write_text("model,accuracy\nA,0.900\n", encoding="utf-8")
            actual.write_text("model,accuracy\nA,0.901\n", encoding="utf-8")

            matching = run_script(
                "compare_result_tables.py",
                expected,
                actual,
                "--keys",
                "model",
                "--metrics",
                "accuracy",
                "--abs-tol",
                "0.002",
            )
            self.assertEqual(matching.returncode, 0, matching.stderr)
            self.assertEqual(json.loads(matching.stdout)["status"], "MATCH")

            mismatching = run_script(
                "compare_result_tables.py",
                expected,
                actual,
                "--keys",
                "model",
                "--metrics",
                "accuracy",
                "--abs-tol",
                "0.0001",
            )
            self.assertEqual(mismatching.returncode, 1, mismatching.stderr)
            self.assertEqual(json.loads(mismatching.stdout)["status"], "MISMATCH")

    def test_missing_expected_metric_is_not_silently_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.csv"
            actual = root / "actual.csv"
            expected.write_text("model,accuracy,f1\nA,0.9,0.8\n", encoding="utf-8")
            actual.write_text("model,accuracy\nA,0.9\n", encoding="utf-8")

            completed = run_script(
                "compare_result_tables.py",
                expected,
                actual,
                "--keys",
                "model",
            )

            self.assertEqual(completed.returncode, 2)
            self.assertIn("metric column is not present in both tables: f1", completed.stderr)


if __name__ == "__main__":
    unittest.main()
