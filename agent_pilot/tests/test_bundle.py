"""Packaging/drift unit tests with fabricated transcripts, NOT execution results.

No candidate is executed here. Integration with the real isolation runtime is a
separate check; mock PASS below must not be reported as real repair performance.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from agent_pilot import bundle, judge


def fake_isolated(source, harness, input_data, **kwargs):
    """Predetermined mock response. This function does not execute source."""
    request, mode = input_data["request"], input_data["auth_mode"]
    valid = (isinstance(request, dict) and isinstance(request.get("request_id"), str)
             and bool(request["request_id"]) and isinstance(request.get("resource"), str)
             and bool(request["resource"]) and type(request.get("units")) is int
             and 1 <= request["units"] <= 5 and type(request.get("debug", False)) is bool)
    rid = request.get("request_id", "") if isinstance(request, dict) else ""
    rid = rid if isinstance(rid, str) else ""
    error = (("invalid_request", "Invalid request") if not valid else
             ("permission_denied", "Permission denied") if mode == "denied" else
             ("auth_unavailable", "Authentication service unavailable") if mode == "provider_error" else None)
    if error:
        returned = {"ok": False, "request_id": rid, "error": {"type": error[0], "message": error[1]}}
    else:
        returned = {"ok": True, "request_id": rid, "resource": request["resource"],
                    "units": request["units"], "total": request["units"] * 7,
                    "subject": "subject:" + request["resource"],
                    "meta": {"route": "local-mock", "debug": request.get("debug", False)}}
    trial = {**input_data, "returned": returned, "raised": None, "stdout": "", "stderr": "",
             "logs": [], "serialization_error": False,
             "auth_calls": [{"credential": input_data["credential"], "resource": request["resource"]}] if valid else []}
    return {"status": "OK", "returncode": 0, "stdout": json.dumps({"schema": judge.SCHEMA, "trial": trial}),
            "stderr": "", "duration_ms": 1, "isolation_receipt": {"profile": "MOCK-NO-EXECUTION"}}


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="credproof-bundle-unit-")
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.run.mkdir()
        # Deliberately does not implement the behavior: tests concern packaging,
        # and fabricated transcripts cannot establish candidate correctness.
        self.code = "import os\n\ndef run(request, auth_service):\n    return {}\n"
        for name in ("original.py", "final-candidate.py"):
            (self.run / name).write_text(self.code, encoding="utf-8", newline="\n")
        rules = bundle._rules_hash((bundle.PACKAGE / "fixtures/requirements.md").read_bytes(),
                                  (bundle.PACKAGE / "judge.py").read_bytes(), bundle._trusted_policy())
        report = {"method": "MOCK", "source_sha256": bundle._sha(self.code.encode()),
                  "candidate_sha256": bundle._sha(self.code.encode()), "rules_sha256": rules,
                  "final_validation": {"verdict": "PASS", "reasons": []},
                  "task": {"task_status": "INCOMPLETE"}, "observations": [], "tool_trace": []}
        bundle._write_json(self.run / "result.json", report)
        bundle._write_json(self.run / "initial-evidence.json", [])
        self.output = self.root / "bundle"

    def tearDown(self):
        self.temporary.cleanup()

    def export(self):
        return bundle.export_bundle(self.run, self.output)

    def test_export_is_allowlisted_redacted_and_never_executes(self):
        (self.run / ".env").write_text("SECRET=DO_NOT_EXPORT", encoding="utf-8")
        (self.run / "private").mkdir()
        (self.run / "private/raw.json").write_text("private", encoding="utf-8")
        (self.run / "model").mkdir()
        bundle._write_json(self.run / "model/model-01-response.json", {"content": "CP_EXEC_" + "a" * 48})
        with patch.object(bundle, "run_isolated") as execute:
            result = self.export()
        execute.assert_not_called()
        self.assertEqual(result["status"], "EXPORTED")
        self.assertFalse((self.output / ".env").exists())
        self.assertFalse((self.output / "private").exists())
        self.assertIn("[REDACTED]", (self.output / "trace/model/model-01-response.json").read_text())
        self.assertEqual((self.output / "current.py").read_text(), self.code)

    def test_rejects_wrong_run_binding_and_existing_destination(self):
        (self.run / "final-candidate.py").write_text(self.code + "# changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "binding_mismatch"):
            self.export()
        self.assertFalse(self.output.exists())
        (self.run / "final-candidate.py").write_text(self.code, encoding="utf-8", newline="\n")
        self.export()
        with self.assertRaises(ValueError):
            self.export()

    def test_private_transcript_in_public_record_is_rejected(self):
        bundle._write_json(self.run / "final-validation.json", {"auth_calls": []})
        with self.assertRaisesRegex(ValueError, "private_trial"):
            self.export()
        self.assertFalse(self.output.exists())

    def test_fresh_calls_all_thirteen_not_report_pass(self):
        self.export()
        with patch.object(bundle, "run_isolated", side_effect=fake_isolated) as execute:
            result = bundle.recheck_bundle(self.output, self.root / "fresh.json")
        self.assertEqual(execute.call_count, 13)
        self.assertEqual(result["validation"]["verdict"], "PASS")
        self.assertTrue(result["prior_report_applicable"])
        self.assertFalse(result["historical_task_status_rewritten"])
        self.assertNotIn("CP_EXEC_", (self.root / "fresh.json").read_text())

    def test_object_change_invalidates_old_but_can_fresh_pass(self):
        self.export()
        (self.output / "current.py").write_text(self.code + "# harmless change\n", encoding="utf-8")
        with patch.object(bundle, "run_isolated", side_effect=fake_isolated):
            result = bundle.recheck_bundle(self.output, self.root / "changed.json")
        self.assertFalse(result["prior_report_applicable"])
        self.assertIn("CANDIDATE_CHANGED", result["prior_report_reasons"])
        self.assertEqual(result["validation"]["verdict"], "PASS")

    def test_report_changed_to_pass_does_not_bypass_unknown(self):
        self.export()
        report_path = self.output / "report.json"
        report = json.loads(report_path.read_text())
        report["final_validation"] = {"verdict": "PASS", "checks_run": 999}
        report_path.write_text(json.dumps(report), encoding="utf-8")
        with patch.object(bundle, "run_isolated", return_value={"status": "ISOLATION_ERROR"}) as execute:
            result = bundle.recheck_bundle(self.output, self.root / "unknown.json")
        self.assertEqual(execute.call_count, 13)
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")
        self.assertFalse(result["prior_report_applicable"])

    def test_fixed_judge_fail_dominates_unavailable_trials(self):
        self.export()
        calls = []
        def one_failure(*args, **kwargs):
            calls.append(1)
            if len(calls) > 1:
                return {"status": "TIMEOUT"}
            result = fake_isolated(*args, **kwargs)
            envelope = json.loads(result["stdout"])
            envelope["trial"]["returned"] = {"ok": True}
            result["stdout"] = json.dumps(envelope)
            return result
        with patch.object(bundle, "run_isolated", side_effect=one_failure):
            result = bundle.recheck_bundle(self.output, self.root / "failed.json")
        self.assertEqual(result["validation"]["verdict"], "FAIL")
        self.assertIn("RESPONSE_CONTRACT", result["validation"]["reasons"])

    def test_config_or_judge_drift_blocks_execution(self):
        self.export()
        (self.output / "configuration.json").write_text(json.dumps({"schema": bundle.SCHEMA,
                                                                  "policy": {}, "required_trials": 0}), encoding="utf-8")
        with patch.object(bundle, "run_isolated") as execute:
            result = bundle.recheck_bundle(self.output, self.root / "config-drift.json")
        execute.assert_not_called()
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")
        self.assertFalse(result["prior_report_applicable"])
        self.assertIn("TRUSTED_MATERIAL_CHANGED", result["validation"]["reasons"])

    def test_modified_packaged_judge_is_not_imported_or_executed(self):
        self.export()
        (self.output / "agent_pilot/judge.py").write_text("raise RuntimeError('DO NOT IMPORT')\n", encoding="utf-8")
        with patch.object(bundle, "run_isolated") as execute:
            result = bundle.recheck_bundle(self.output, self.root / "judge-drift.json")
        execute.assert_not_called()
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")
        self.assertIn("LOADED_VERIFIER_DIFFERS_FROM_BUNDLE", result["validation"]["reasons"])

    def test_missing_current_or_malformed_manifest_is_unknown(self):
        self.export()
        (self.output / "current.py").unlink()
        with patch.object(bundle, "run_isolated") as execute:
            result = bundle.recheck_bundle(self.output, self.root / "missing-current.json")
        execute.assert_not_called()
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")
        (self.output / "manifest.json").write_text("[]", encoding="utf-8")
        result = bundle.recheck_bundle(self.output, self.root / "malformed.json")
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")

    def test_unsafe_source_is_not_executed_and_existing_report_not_overwritten(self):
        self.export()
        (self.output / "current.py").write_text("import subprocess\n", encoding="utf-8")
        target = self.root / "static-fail.json"
        with patch.object(bundle, "run_isolated") as execute:
            result = bundle.recheck_bundle(self.output, target)
        execute.assert_not_called()
        self.assertEqual(result["validation"]["verdict"], "FAIL")
        original = target.read_bytes()
        with self.assertRaises(ValueError):
            bundle.recheck_bundle(self.output, target)
        self.assertEqual(target.read_bytes(), original)

    def test_changed_during_recheck_is_unknown(self):
        self.export()
        def mutation(*args, **kwargs):
            (self.output / "current.py").write_text(self.code + "# concurrent edit\n", encoding="utf-8")
            return fake_isolated(*args, **kwargs)
        with patch.object(bundle, "run_isolated", side_effect=mutation):
            result = bundle.recheck_bundle(self.output, self.root / "race.json")
        self.assertEqual(result["validation"]["verdict"], "UNKNOWN")
        self.assertIn("MATERIAL_CHANGED_DURING_RECHECK", result["validation"]["reasons"])

    def test_portable_import_and_help_need_no_checkout_or_qwen(self):
        self.export()
        moved = self.root / "clean-directory"
        shutil.copytree(self.output, moved)
        shutil.rmtree(self.output)
        env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME"}}
        result = subprocess.run([sys.executable, "-S", "-m", "agent_pilot.bundle", "--help"],
                                cwd=moved, env=env, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("recheck", result.stdout)


if __name__ == "__main__":
    unittest.main()
