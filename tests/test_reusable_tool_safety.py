"""Focused regressions for the reusable project entry (no model/GPU required).

These tests exercise configuration and evidence boundaries.  The real isolated
execution receipts are kept separately in experiments/reusable-tool-safety.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import types
import unittest
from unittest.mock import patch

from credproof_safety.cli import main
from credproof_safety.config import load_config, template
from credproof_safety.project import _verdict, export_regression_tests


class ReusableSafetyRegressionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="credproof-api-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.config_path = self.root / "credproof.toml"
        self.config_path.write_text(template(self.root), encoding="utf-8")

    def _config_with(self, before, after):
        text = template(self.root)
        self.assertIn(before, text)
        self.config_path.write_text(text.replace(before, after), encoding="utf-8")
        return load_config(self.config_path)

    def _complete_execution(self):
        return {
            "status": "OK",
            "pytest_exit_code": 0,
            "entry_returned": {"resource": "demo"},
            "raised": None,
            "forbidden_reads": [],
            "audit_events": [{"classification": "allowed", "event": "open"}],
            "credential_leaks": [],
            "requests": [{"service": "allow", "path": "/api", "credential_ok": True}],
            "unauthorized_connections": [],
            "isolation": {"pytest_collection_in_sandbox": True, "uncovered": []},
        }

    def test_invalid_schema_is_rejected_before_execution(self):
        with self.assertRaisesRegex(ValueError, "schema"):
            self._config_with("credproof.project-safety/v1", "other/v1")

    def test_parent_traversal_in_test_scope_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "inside the project"):
            self._config_with('tests = ["tests"]', 'tests = ["../outside-tests"]')

    def test_absolute_allowed_directory_is_rejected(self):
        with self.assertRaises(ValueError):
            self._config_with('allowed_dirs = ["data"]', 'allowed_dirs = ["/outside"]')

    def test_same_allowed_and_forbidden_directory_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            self._config_with('forbidden_dirs = ["secrets"]', 'forbidden_dirs = ["data"]')

    def test_noninteger_port_and_nonidentifier_entry_are_rejected(self):
        for before, after in (
            ('port = 0', 'port = true'),
            ('module = "tool"', 'module = "../tool"'),
        ):
            with self.subTest(after=after):
                with self.assertRaises(ValueError):
                    self._config_with(before, after)

    def test_incomplete_and_blocked_execution_never_pass(self):
        config = load_config(self.config_path)
        for status in (None, "BLOCKED", "ERROR", "TIMEOUT"):
            with self.subTest(status=status):
                result = _verdict(config, {"status": status})
                self.assertEqual("UNKNOWN", result["verdict"])
                self.assertTrue(result["observation_summary"]["incomplete"])
                self.assertEqual(status == "BLOCKED", result["observation_summary"]["outer_sandbox_blocked"])

    def test_missing_required_receipts_never_pass(self):
        config = load_config(self.config_path)
        execution = self._complete_execution()
        del execution["pytest_exit_code"]
        del execution["isolation"]
        result = _verdict(config, execution)
        self.assertNotEqual("PASS", result["verdict"])

    def test_pass_requires_business_and_security_checks(self):
        config = load_config(self.config_path)
        execution = self._complete_execution()
        self.assertEqual("PASS", _verdict(config, execution)["verdict"])
        for field, value, failed_check in (
            ("pytest_exit_code", 1, "pytest"),
            ("forbidden_reads", ["/tmp/lab/forbidden/secret.txt"], "no_forbidden_file_read"),
            ("credential_leaks", ["return"], "no_credential_output"),
            ("unauthorized_connections", ["forbidden socket"], "no_unauthorized_connection"),
            ("requests", [], "allowed_service_receipt"),
        ):
            with self.subTest(field=field):
                changed = self._complete_execution()
                changed[field] = value
                result = _verdict(config, changed)
                self.assertEqual("FAIL", result["verdict"])
                self.assertIn(failed_check, result["failed_checks"])

    def test_init_preview_does_not_write_and_write_does_not_overwrite(self):
        destination = self.root / "new.toml"
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(["init", "--project", str(self.root), "--config", str(destination)])
        self.assertEqual(0, exit_code)
        self.assertEqual("would_create", json.loads(out.getvalue())["action"])
        self.assertFalse(destination.exists())
        original = self.config_path.read_bytes()
        out = io.StringIO()
        with redirect_stdout(out):
            exit_code = main(["init", "--project", str(self.root), "--write"])
        self.assertEqual(0, exit_code)
        self.assertEqual("refuse_to_overwrite", json.loads(out.getvalue())["action"])
        self.assertEqual(original, self.config_path.read_bytes())

    def test_explicit_init_write_creates_valid_config(self):
        destination = self.root / "new.toml"
        with redirect_stdout(io.StringIO()):
            exit_code = main(["init", "--project", str(self.root), "--config", str(destination), "--write"])
        self.assertEqual(0, exit_code)
        self.assertEqual(self.root.resolve(), load_config(destination).project_root.resolve())

    def test_export_refuses_overwrite(self):
        destination = self.root / "regression"
        export_regression_tests(self.config_path, destination)
        (destination / "retain.txt").write_text("existing user material", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            export_regression_tests(self.config_path, destination)
        self.assertEqual("existing user material", (destination / "retain.txt").read_text(encoding="utf-8"))

    def test_exported_assertion_reruns_check_and_rejects_later_failure(self):
        destination = export_regression_tests(self.config_path, self.root / "regression")
        # pytest is not needed on the host for this protocol-level test.  The
        # generated assertion still runs its actual code and imports the public
        # check API; only that expensive sandbox execution is substituted.
        pytest_stub = types.ModuleType("pytest")
        pytest_stub.mark = types.SimpleNamespace(credproof_safety=lambda function: function)
        pytest_stub.skip = lambda message: (_ for _ in ()).throw(RuntimeError(message))
        with patch.dict("sys.modules", {"pytest": pytest_stub}), patch.dict(
            os.environ, {"CREDPROOF_PROJECT_ROOT": str(self.root), "CREDPROOF_INNER": "0"}
        ), patch("credproof_safety.check_project", side_effect=[{"verdict": "PASS"}, {"verdict": "FAIL"}]) as check:
            generated = runpy.run_path(str(destination / "test_credproof_safety.py"))
            generated["test_credproof_safety_regression"]()
            with self.assertRaises(AssertionError):
                generated["test_credproof_safety_regression"]()
        self.assertEqual(2, check.call_count)
        for call in check.call_args_list:
            self.assertEqual(self.root / "credproof.toml", call.args[0])
            self.assertEqual(self.root, call.kwargs["project_root"])


if __name__ == "__main__":
    unittest.main()
