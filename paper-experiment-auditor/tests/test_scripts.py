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

    def test_depth_and_custom_exclusion_are_respected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keep").mkdir()
            (root / "skip").mkdir()
            (root / "deep" / "nested").mkdir(parents=True)
            (root / "keep" / "visible.py").write_text("pass\n", encoding="utf-8")
            (root / "skip" / "hidden.py").write_text("pass\n", encoding="utf-8")
            (root / "deep" / "nested" / "too_deep.py").write_text("pass\n", encoding="utf-8")

            completed = run_script(
                "collect_repo_structure.py",
                root,
                "--max-depth",
                1,
                "--exclude",
                "skip",
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            paths = [item["path"] for item in json.loads(completed.stdout)["files"]]
            self.assertEqual(paths, ["keep/visible.py"])


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

    def test_ini_and_nested_lists_are_flattened(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ini_path = root / "train.ini"
            json_path = root / "augmentations.json"
            ini_path.write_text("[training]\nepochs = 10\n", encoding="utf-8")
            json_path.write_text(json.dumps({"steps": [{"name": "crop"}, {"name": "flip"}]}), encoding="utf-8")

            completed = run_script("collect_config_values.py", ini_path, json_path)

            self.assertEqual(completed.returncode, 0, completed.stderr)
            records = {(row["source"], row["key"]): row["value"] for row in json.loads(completed.stdout)["records"]}
            self.assertEqual(records[(ini_path.name, "training.epochs")], "10")
            self.assertEqual(records[(json_path.name, "steps[1].name")], "flip")


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

    def test_missing_and_extra_rows_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.csv"
            actual = root / "actual.csv"
            expected.write_text("model,accuracy\nA,0.9\nB,0.8\n", encoding="utf-8")
            actual.write_text("model,accuracy\nA,0.9\nC,0.7\n", encoding="utf-8")

            completed = run_script("compare_result_tables.py", expected, actual, "--keys", "model")

            self.assertEqual(completed.returncode, 1, completed.stderr)
            kinds = [item["kind"] for item in json.loads(completed.stdout)["differences"]]
            self.assertEqual(kinds, ["missing-row", "extra-row"])

    def test_duplicate_row_keys_are_input_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "expected.csv"
            actual = root / "actual.csv"
            expected.write_text("model,accuracy\nA,0.9\nA,0.8\n", encoding="utf-8")
            actual.write_text("model,accuracy\nA,0.9\n", encoding="utf-8")

            completed = run_script("compare_result_tables.py", expected, actual, "--keys", "model")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("duplicate key", completed.stderr)


class ReleasePackageCheckTests(unittest.TestCase):
    def make_repo(self, directory: str) -> Path:
        root = Path(directory)
        files = {
            "README.md": "# readme\n",
            "requirements.txt": "numpy\n",
            "src/prepare.py": "print('ok')\n",
            "src/train.py": "print('ok')\n",
            "src/evaluate.py": "print('ok')\n",
            "src/plot.py": "print('ok')\n",
            "configs/train.json": "{}",
            "checkpoints/model.pt": "weights",
            "results/summary.csv": "a,b\n1,2\n",
        }
        for rel, content in files.items():
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def manifest(self) -> dict[str, object]:
        return {
            "schema_version": "1.0",
            "repository": ".",
            "documentation": ["README.md"],
            "install": {
                "command": "pip install -r requirements.txt",
                "environment_files": ["requirements.txt"],
            },
            "data_preparation": {"command": "python src/prepare.py", "entry": "src/prepare.py"},
            "training": {"command": "python src/train.py", "entry": "src/train.py"},
            "evaluation": {"command": "python src/evaluate.py", "entry": "src/evaluate.py"},
            "result_generation": {"command": "python src/plot.py", "entry": "src/plot.py"},
            "default_configs": ["configs/train.json"],
            "checkpoints": {"acquisition": "bundled", "paths": ["checkpoints/model.pt"]},
            "expected_outputs": ["results/summary.csv"],
            "license": "MIT",
            "data_restrictions": "",
        }

    def write_and_run(self, root: Path, manifest: dict[str, object]) -> subprocess.CompletedProcess[str]:
        path = root / "release-manifest.json"
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return run_script("check_release_package.py", path, "--repo-root", root)

    def test_existing_assets_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            completed = self.write_and_run(root, self.manifest())
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["findings"], [])

    def test_missing_asset_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            manifest = self.manifest()
            manifest["expected_outputs"] = ["results/missing.csv"]  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("MISSING_RELEASE_ASSET", categories)

    def test_unsafe_path_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            manifest = self.manifest()
            manifest["documentation"] = ["../README.md"]  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("UNSAFE_PATH", categories)

    def test_sensitive_filename_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            manifest = self.manifest()
            manifest["documentation"] = [".env"]  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("SENSITIVE_CONTENT_RISK", categories)

    def test_unlisted_sensitive_filename_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            (root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
            completed = self.write_and_run(root, self.manifest())
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("SENSITIVE_CONTENT_RISK", categories)

    def test_missing_manifest_contract_fields_are_errors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            manifest = self.manifest()
            manifest.pop("license")
            manifest.pop("data_restrictions")
            manifest["training"]["command"] = ""  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 2, completed.stderr or completed.stdout)
        report = json.loads(completed.stdout)
        self.assertFalse(report["valid"])
        self.assertTrue(any("license" in item for item in report["errors"]))

    def test_external_checkpoint_cannot_have_bundled_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            manifest = self.manifest()
            manifest["checkpoints"] = {"acquisition": "download from https://example.org/model", "paths": ["checkpoints/model.pt"]}
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("INVALID_CONFIG", categories)

    def test_local_absolute_command_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            manifest = self.manifest()
            manifest["training"]["command"] = "python C:/Users/alice/private/train.py"  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("UNSAFE_PATH", categories)

    def test_parent_symlink_escape_is_reported_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as outside:
            root = self.make_repo(directory)
            outside_root = Path(outside)
            (outside_root / "README.md").write_text("outside\n", encoding="utf-8")
            link = root / "linked"
            try:
                link.symlink_to(outside_root, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation is not available")
            manifest = self.manifest()
            manifest["documentation"] = ["linked/README.md"]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("UNSAFE_PATH", categories)

    def test_invalid_json_config_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = self.make_repo(directory)
            (root / "configs" / "bad.json").write_text("{not valid json", encoding="utf-8")
            manifest = self.manifest()
            manifest["default_configs"] = ["configs/bad.json"]  # type: ignore[index]
            completed = self.write_and_run(root, manifest)
        self.assertEqual(completed.returncode, 1, completed.stderr or completed.stdout)
        categories = [item["category"] for item in json.loads(completed.stdout)["findings"]]
        self.assertIn("INVALID_CONFIG", categories)


if __name__ == "__main__":
    unittest.main()
