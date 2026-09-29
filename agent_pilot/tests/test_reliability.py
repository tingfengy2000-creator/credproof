"""Reliability unit tests with fabricated transcripts and mocked execute/verify.

These test permission/state transitions, not model quality or real isolation.
Candidate source is never executed; the real isolation entry point is blocked.
"""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from agent_pilot import reliability as rel
from agent_pilot.tools import dispatch


SOURCE = "def run(request, auth_service):\n    return {}\n"
SECRET = "CP_EXEC_UNIT_ONLY_" + "abcd" * 12
TRIGGER = {
    "request": {"request_id": "unit-request", "resource": "unit-resource", "units": 2},
    "auth_mode": "success",
}
PASS = {"verdict": "PASS", "reasons": [], "leak_channels": []}
UNKNOWN = {"verdict": "UNKNOWN", "reasons": ["unit_execution_unavailable"], "leak_channels": []}


def fabricated_trial(trigger=None, leak=False):
    """A hand-built oracle input, never an observed candidate execution."""
    trigger = copy.deepcopy(trigger or TRIGGER)
    request = trigger["request"]
    response = {
        "ok": True, "request_id": request["request_id"], "resource": request["resource"],
        "units": request["units"], "total": request["units"] * 7,
        "subject": "subject:" + request["resource"],
        "meta": {"route": "local-mock", "debug": request.get("debug", False)},
    }
    if leak:
        response["diagnostic"] = {"nested": [SECRET]}
    return {
        **trigger, "credential": SECRET, "returned": response, "raised": None,
        "stdout": "", "stderr": "", "logs": [], "serialization_error": False,
        "auth_calls": [{"credential": SECRET, "resource": request["resource"]}],
    }


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="credproof-reliability-unit-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rules = patch.object(rel, "rules_hash", return_value="unit-rules-v1").start()
        self.addCleanup(patch.stopall)
        self.isolation = patch(
            "agent_pilot.experiment.run_isolated",
            side_effect=AssertionError("Unit tests must never execute candidate code"),
        ).start()
        self.session = rel.GovernedSession(SOURCE, self.root / "session", self.root / "private")
        self.session.execute = Mock(return_value=(fabricated_trial(), None))
        self.session.verify = Mock(return_value=copy.deepcopy(PASS))

    def tearDown(self):
        self.isolation.assert_not_called()

    def observe(self, *, leak=False, trigger=None, source=None):
        self.session.execute.return_value = (fabricated_trial(trigger, leak=leak), None)
        return self.session.observe(source or self.session.source, copy.deepcopy(trigger or TRIGGER),
                                    "Unit hypothesis: inspect forbidden output")

    def propose(self, suffix="one"):
        return self.session.submit({"path": "tool.py", "content": SOURCE + "\n# " + suffix + "\n",
                                    "rationale": "Unit proposal; not an executed repair"})

    def test_no_evidence_rejects_submit_without_writing_candidate(self):
        response = dispatch(self.session.tools(), "submit_patch", {
            "path": "tool.py", "content": SOURCE + "\n# proposed\n", "rationale": "Suspicion only",
        })
        self.assertEqual(response["status"], "REJECTED")
        self.assertFalse(self.session.candidates)
        self.assertFalse(list(self.session.output.glob("candidate-*")))
        self.assertEqual(self.session.authority()["confirmed"], "UNKNOWN")
        self.session.verify.assert_not_called()

    def test_authorized_authentication_is_not_a_leak(self):
        receipt = self.observe()
        self.assertEqual(receipt["observation"]["verdict"], "PASS")
        self.assertEqual(self.session.authority()["confirmed"], "NO_LEAK_OBSERVED")
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")
        self.assertNotIn(SECRET, json.dumps(receipt))

    def test_confirmed_forbidden_channel_allows_only_the_named_source_path(self):
        receipt = self.observe(leak=True)
        self.assertEqual(receipt["observation"]["verdict"], "FAIL")
        self.assertTrue(self.session.authority()["repair_authorized"])
        self.assertNotIn(SECRET, json.dumps(receipt))
        for path in ("../tool.py", "/tmp/tool.py", "judge.py"):
            with self.subTest(path=path):
                result = dispatch(self.session.tools(), "submit_patch", {
                    "path": path, "content": SOURCE, "rationale": "Unit invalid path",
                })
                self.assertEqual(result["status"], "REJECTED")
        result = self.propose()
        self.assertEqual(result["candidate_id"], "candidate-1")
        self.assertTrue((self.session.output / "candidate-1.py").is_file())

    def test_source_drift_revokes_repair_permission(self):
        self.observe(leak=True)
        self.session.source += "\n# changed original\n"
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")

    def test_rules_drift_revokes_permission_even_after_new_observation(self):
        self.observe(leak=True)
        self.rules.return_value = "unit-rules-v2"
        self.observe(leak=True)
        self.assertEqual(self.session.execute.call_count, 2)
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")

    def test_conditions_drift_invalidates_receipt(self):
        receipt = self.observe(leak=True)
        receipt["conditions"]["request"]["units"] = 5
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")

    def test_candidate_evidence_cannot_authorize_original_modification(self):
        self.observe(leak=True, source=SOURCE + "\n# different object\n")
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")

    def test_unavailable_observation_remains_unknown_and_cannot_authorize(self):
        self.session.execute.return_value = (None, copy.deepcopy(UNKNOWN))
        receipt = self.session.observe(SOURCE, copy.deepcopy(TRIGGER), "Unit unavailable run")
        self.assertEqual(receipt["observation"]["verdict"], "UNKNOWN")
        self.assertEqual(self.session.authority()["confirmed"], "UNKNOWN")
        self.assertFalse(self.session.authority()["repair_authorized"])
        self.assertEqual(self.propose()["status"], "REJECTED")

    def test_identical_observation_is_cached_but_changed_conditions_execute(self):
        first = self.observe()
        second = self.observe()
        self.assertEqual(second["id"], first["id"])
        self.assertTrue(second["cached_same_object_and_conditions"])
        self.assertEqual(self.session.execute.call_count, 1)
        changed = copy.deepcopy(TRIGGER)
        changed["request"]["units"] = 4
        third = self.observe(trigger=changed)
        self.assertNotEqual(third["id"], first["id"])
        self.assertEqual(self.session.execute.call_count, 2)
        self.assertNotEqual(third["conditions_sha256"], first["conditions_sha256"])

    def test_changed_source_does_not_reuse_observation(self):
        self.observe()
        self.observe(source=SOURCE + "\n# second source\n")
        self.assertEqual(self.session.execute.call_count, 2)

    def test_three_repeated_observations_stop_unknown_without_reexecution(self):
        self.observe()
        for _ in range(3):
            self.observe()
        self.assertEqual(self.session.execute.call_count, 1)
        self.assertEqual(self.session.terminal["task_status"], "UNKNOWN")

    def test_old_candidate_pass_cannot_complete_latest_candidate(self):
        self.observe(leak=True)
        self.propose("first")
        self.propose("second")
        result = self.session.check("candidate-1")
        self.assertEqual(result["verdict"], "PASS")
        self.assertIsNone(self.session.terminal)
        self.session.check("candidate-2")
        self.assertEqual(self.session.terminal["candidate_id"], "candidate-2")
        self.assertEqual(self.session.terminal["task_status"], "COMPLETED_REPAIRED")

    def test_rules_changing_during_validation_cannot_complete(self):
        def changed_rules(*args):
            self.rules.return_value = "unit-rules-changed-during-verify"
            return copy.deepcopy(PASS)
        self.session.verify.side_effect = changed_rules
        self.session.check("original")
        self.assertIsNone(self.session.terminal)

    def test_candidate_changing_during_validation_cannot_complete(self):
        self.observe(leak=True)
        self.propose()
        def changed_candidate(*args):
            self.session.candidates["candidate-1"] += "\n# changed while verifying\n"
            return copy.deepcopy(PASS)
        self.session.verify.side_effect = changed_candidate
        self.session.check("candidate-1")
        self.assertIsNone(self.session.terminal)

    def test_verification_cache_requires_same_source_and_rules(self):
        self.observe(leak=True)
        self.propose("first")
        self.propose("second")
        self.session.check("candidate-1")
        cached = self.session.check("candidate-1")
        self.assertTrue(cached["cached_same_object_and_rules"])
        self.assertEqual(self.session.verify.call_count, 1)
        self.session.check("candidate-2")
        self.assertEqual(self.session.verify.call_count, 2)
        self.rules.return_value = "unit-rules-v2"
        result = self.session.check("candidate-2")
        self.assertFalse(result["cached_same_object_and_rules"])
        self.assertEqual(self.session.verify.call_count, 3)

    def test_unknown_required_verification_is_not_completion(self):
        self.session.verify.return_value = copy.deepcopy(UNKNOWN)
        self.session.check("original")
        self.assertEqual(self.session.terminal["task_status"], "UNKNOWN")

    def test_unknown_trial_projection(self):
        # All input slots are present, but one transcript is not trustworthy.
        # This fabricated aggregate tests display projection only, not execution.
        aggregate = {"verdict": "UNKNOWN", "reasons": ["INVALID_TRANSCRIPT"],
                     "checks_run": 13, "leak_channels": [],
                     "trial_counts": {"PASS": 12, "UNKNOWN": 1}}
        with patch.object(rel.Session, "verify", return_value=copy.deepcopy(aggregate)):
            result = rel.GovernedSession.verify(self.session, SOURCE, "unknown-projection")
        checks = {item["id"]: item["status"] for item in result["checks"]}
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertEqual(checks["source-boundary"], "PASS")
        self.assertEqual(checks["credential-channels"], "UNKNOWN")
        self.assertEqual(checks["behavior"], "UNKNOWN")
        self.assertEqual(checks["coverage"], "UNKNOWN")

    def test_failed_required_verification_does_not_complete(self):
        self.session.verify.return_value = {"verdict": "FAIL", "reasons": ["RESPONSE_CONTRACT"]}
        self.session.check("original")
        self.assertIsNone(self.session.terminal)

    def test_fourth_proposal_is_rejected_without_candidate_write(self):
        self.observe(leak=True)
        for index in range(3):
            self.propose(str(index))
        self.assertEqual(self.propose("fourth")["reason"], "candidate_budget_exhausted")
        self.assertEqual(len(self.session.candidates), 3)
        self.assertFalse((self.session.output / "candidate-4.py").exists())

    def test_unknown_evidence_id_returns_controlled_rejection(self):
        response = dispatch(self.session.tools(), "get_evidence", {"evidence_id": "not-present"})
        self.assertEqual(response["status"], "REJECTED")

    def test_model_limit_or_error_cannot_be_upgraded_by_independent_final_pass(self):
        # Model stub returns a retained valid JSON despite a terminal error/limit.
        # The final verifier stub's PASS is only a state-transition input.
        for method in ("C-agent", "B-once", "D-no-feedback-1"):
            for status in ("STOPPED_LIMIT", "ERROR"):
                with self.subTest(method=method, status=status):
                    output = self.root / (method + "-" + status)
                    model = {"status": status, "error": "Unit exhausted/failed call", "model_calls": 1,
                             "messages": [{"role": "assistant", "content": json.dumps({
                                 "diagnosis": "Unit retained content", "initially_leaking": False,
                                 "code": SOURCE})}]}
                    with patch.object(rel.GovernedSession, "initialize"), \
                         patch.object(rel.GovernedSession, "verify", return_value=copy.deepcopy(PASS)), \
                         patch.object(rel, "LocalAgentClient") as client:
                        client.return_value.run.return_value = model
                        row = rel.run_method(method, SOURCE, output, output.with_name(output.name + "-private"))
                    self.assertEqual(row["final_validation"]["verdict"], "PASS")
                    self.assertFalse(row["task"]["task_status"].startswith("COMPLETED"))
                    self.assertEqual(row["model"]["status"], status)

    def test_fresh_final_unknown_downgrades_previous_executor_completion(self):
        # Actual StrictTool/Session control flow, but no model or candidate run.
        def create_client(**kwargs):
            def fake_client_run(*args):
                dispatch(kwargs["tools"], "verify_patch", {
                    "candidate_id": "original", "initially_leaking": False, "diagnosis": "Unit clean original",
                })
                return {"status": "EXECUTOR_COMPLETED", "messages": [], "model_calls": 0,
                        "executor_result": kwargs["execution_completion"]()}
            return Mock(run=fake_client_run)
        with patch.object(rel.GovernedSession, "initialize"), \
             patch.object(rel.GovernedSession, "verify", side_effect=[copy.deepcopy(PASS), copy.deepcopy(UNKNOWN)]), \
             patch.object(rel, "LocalAgentClient", side_effect=create_client):
            row = rel.run_method("C-agent", SOURCE, self.root / "fresh", self.root / "fresh-private")
        self.assertEqual(row["final_validation"]["verdict"], "UNKNOWN")
        self.assertEqual(row["task"]["task_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
