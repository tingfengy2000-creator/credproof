"""Static contract checks for the model-process boundary launcher.

These tests do not stand in for the real WSL run.  The public acceptance record
contains the fresh boundary probe and the finite model trace; this file guards
against accidentally reverting to the old whole-checkout launcher.
"""
from pathlib import Path
import hashlib
import json
import unittest

from credproof_safety.agent import _model_feedback, _model_initial_context, _phase_rejection, _read_progress_update
from agent_pilot.model_client import compact_messages_for_budget, to_ollama_messages
from credproof_safety.config import load_config


SOURCE = Path(__file__).resolve().parents[2] / "credproof_safety" / "agent.py"


class ModelBoundaryContractTests(unittest.TestCase):
    def test_launcher_uses_allowlist_and_private_namespace(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("_MODEL_BOUNDARY_BOOTSTRAP", text)
        self.assertIn("'--unshare-all'", text)
        self.assertIn("'--disable-userns'", text)
        self.assertIn("'--ro-bind', str(stage), '/app'", text)
        self.assertIn("'--ro-bind', str(deps), '/deps'", text)
        self.assertIn("'--bind', str(work_source), '/work'", text)
        self.assertIn("'--bind', str(rpc_source), '/rpc'", text)
        self.assertIn("'--dev-bind', '/dev/dxg', '/dev/dxg'", text)
        self.assertIn("initial-context.json", text)
        self.assertIn("'/usr/lib/wsl/drivers'", text)
        self.assertIn("'OLLAMA_LLM_LIBRARY', 'cuda_v12'", text)

    def test_model_does_not_receive_checkout_or_artifact_root(self):
        text = SOURCE.read_text(encoding="utf-8")
        bootstrap = text.split("_MODEL_BOUNDARY_BOOTSTRAP = r'''", 1)[1].split("'''", 1)[0]
        self.assertNotIn("ro-bind', str(repo)", bootstrap)
        self.assertIn("'checkout', 'repair artifact root'", bootstrap)
        self.assertIn("CREDPROOF_HOST_SENTINEL", text)

    def test_rpc_is_native_wsl_path_and_public_copy_is_record_only(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("rpc_native = paths['root'] + '/model-rpc-'", text)
        self.assertIn("native_requests()", text)
        self.assertIn("native_response(ident, value)", text)
        self.assertIn("model_boundary", text)

    def test_feedback_exposes_declared_business_files_and_contract(self):
        config = load_config(Path(__file__).resolve().parents[2] / "examples/material_assistant/credproof.toml")
        feedback = _model_feedback({"verdict": "FAIL", "execution": {}}, config)
        self.assertIn("tool.py", feedback["readable_paths"])
        self.assertIn("tests/test_business.py", feedback["readable_paths"])
        self.assertEqual(feedback["repair_guidance"]["entry_path"], "tool.py")
        self.assertIn("allowed mock service", feedback["repair_guidance"]["normal_case"])

    def test_initial_context_is_an_index_without_raw_report_rows(self):
        config = load_config(Path(__file__).resolve().parents[2] / "examples/material_assistant/credproof.toml")
        initial = {
            "verdict": "FAIL",
            "observation_summary": {"classification": "ACTUAL_VIOLATION"},
            "project_tree_sha256": "object-test",
            "execution": {
                "stdout": "[SYNTHETIC_CREDENTIAL] must not be copied",
                "entry_scenarios": [{"entry_returned": {"credential": "[SYNTHETIC_CREDENTIAL]"}}],
            },
        }
        context = _model_initial_context(initial, config)
        self.assertEqual(context["object_id"], "object-test")
        self.assertEqual(context["project"]["readable_paths"], ["tool.py", "tests/test_business.py"])
        self.assertEqual([item["name"] for item in context["project"]["scenarios"]],
                         ["normal_allowed_output", "allowed_file_redirect"])
        self.assertNotIn("stdout", context)
        self.assertNotIn("entry_returned", str(context))

    def test_feedback_omits_raw_output_and_keeps_scenario_status(self):
        config = load_config(Path(__file__).resolve().parents[2] / "examples/material_assistant/credproof.toml")
        report = {
            "verdict": "FAIL", "failed_checks": ["no_credential_output"],
            "required_checks": {"no_credential_output": False},
            "project_tree_sha256": "object-test", "execution": {
                "stdout": "[SYNTHETIC_CREDENTIAL] raw should stay in artifact",
                "credential_leaks": ["return"],
                "entry_scenarios": [{"name": "normal_allowed_output", "expected_error": None,
                                      "require_network": False,
                                      "entry_returned": {"credential": "[SYNTHETIC_CREDENTIAL]"},
                                      "request_observations": [{"service": "allow", "path": "/api"}]}],
            },
        }
        feedback = _model_feedback(report, config)
        self.assertEqual(feedback["object_id"], "object-test")
        self.assertEqual(feedback["scenario_summary"][0]["observed"], "returned")
        self.assertNotIn("[SYNTHETIC_CREDENTIAL]", json.dumps(feedback, ensure_ascii=False))
        self.assertIn("stdout", feedback["omitted_fields"])

    def test_phase_protocol_never_verifies_without_candidate(self):
        required = {"tool.py", "tests/test_business.py"}
        self.assertEqual(
            _phase_rejection("verify_patch", evidence_ready=True,
                             read_paths=required, required_read_paths=required,
                             accepted_candidates=0),
            "NO_ACCEPTED_CANDIDATE")
        self.assertIsNone(
            _phase_rejection("verify_patch", evidence_ready=True,
                             read_paths=required, required_read_paths=required,
                             accepted_candidates=1))

    def test_phase_protocol_requires_evidence_and_all_declared_sources(self):
        required = {"tool.py", "tests/test_business.py"}
        self.assertEqual(
            _phase_rejection("read_code", evidence_ready=False,
                             read_paths=set(), required_read_paths=required,
                             accepted_candidates=0),
            "evidence_required_before_read_code")
        self.assertEqual(
            _phase_rejection("submit_patch", evidence_ready=True,
                             read_paths={"tool.py"}, required_read_paths=required,
                             accepted_candidates=0),
            "required_sources_not_read")

    def test_same_read_progress_stops_after_real_repeats(self):
        key = ("tool.py", "sha-current", 1, "FAIL")
        previous = None
        count = 0
        blocked = False
        for expected in (1, 2):
            previous, count, blocked = _read_progress_update(key, previous, count)
            self.assertEqual(count, expected)
            self.assertFalse(blocked)
        previous, count, blocked = _read_progress_update(key, previous, count)
        self.assertEqual(count, 3)
        self.assertTrue(blocked)
        _, reset_count, reset_blocked = _read_progress_update(
            ("tool.py", "sha-new", 2, "FAIL"), previous, count)
        self.assertEqual(reset_count, 1)
        self.assertFalse(reset_blocked)

    def test_budget_compaction_keeps_current_source_feedback_and_native_pairs(self):
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "function_call": {"name": "get_evidence", "arguments": "{}"},
             "extra": {"function_id": "e"}},
            {"role": "function", "content": json.dumps({"status": "OK", "readable_paths": ["tool.py", "tests/test_business.py"]}), "extra": {"function_id": "e"}},
            {"role": "assistant", "content": "", "function_call": {"name": "read_code", "arguments": "{\"path\":\"tool.py\"}"},
             "extra": {"function_id": "r"}},
            {"role": "function", "content": json.dumps({"status": "OK", "path": "tool.py", "code": "ORIGINAL = 1"}), "extra": {"function_id": "r"}},
            {"role": "assistant", "content": "", "function_call": {"name": "submit_patch", "arguments": "{\"code\":\"x\"}"},
             "extra": {"function_id": "s"}},
            {"role": "function", "content": json.dumps({"status": "ACCEPTED_FOR_VERIFICATION", "candidate": 1, "executor_state": {"phase": "candidate_submitted"}}), "extra": {"function_id": "s"}},
            {"role": "assistant", "content": "", "function_call": {"name": "verify_patch", "arguments": "{}"},
             "extra": {"function_id": "v"}},
            {"role": "function", "content": json.dumps({"status": "OK", "report": {"verdict": "FAIL", "reason": "business"}}), "extra": {"function_id": "v"}},
            {"role": "assistant", "content": "", "function_call": {"name": "get_evidence", "arguments": "{}"},
             "extra": {"function_id": "rejected"}},
            {"role": "function", "content": json.dumps({"status": "REJECTED", "reason": "tool_call_budget_exhausted"}), "extra": {"function_id": "rejected"}},
        ]
        compacted = compact_messages_for_budget(messages)
        wire = to_ollama_messages(compacted)
        self.assertGreaterEqual(len(compacted), 8)
        payload = json.dumps(wire, ensure_ascii=False)
        self.assertIn('\\"code\\":\\"x\\"', payload)
        # This read predates the accepted candidate, so it is stale and may
        # be removed; the accepted submit pair remains the current source.
        self.assertNotIn('ORIGINAL = 1', payload)
        self.assertIn('\\"verdict\\":\\"FAIL\\"', payload)
        self.assertIn('\\"reason\\": \\"tool_call_budget_exhausted\\"', payload)
        self.assertTrue(any(item.get("tool_call_id") == "rejected" for item in wire))
        self.assertTrue(any(item.get("role") == "user" and
                            "executor-context/v1" in item.get("content", "")
                            for item in wire))

    def test_latest_read_and_executor_state_survive_after_accepted_candidate(self):
        messages = [
            {"role": "system", "content": "system"}, {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "function_call": {"name": "submit_patch", "arguments": json.dumps({"code": "CURRENT = 2"})}, "extra": {"function_id": "submit"}},
            {"role": "function", "content": json.dumps({
                "status": "ACCEPTED_FOR_VERIFICATION", "candidate": 1,
                "candidate_sha256": hashlib.sha256(b"CURRENT = 2").hexdigest(), "verification_action": "program_auto_verify",
                "verification": {"status": "OK", "report": {"verdict": "FAIL", "reason": "return_leak"}},
                "executor_state": {"phase": "candidate_verified", "current_candidate": 1,
                                    "remaining_tool_calls": 7, "next_action": "review_verification_and_submit_new_candidate_or_stop"},
            }), "extra": {"function_id": "submit"}},
            {"role": "assistant", "content": "", "function_call": {"name": "read_code", "arguments": '{"path":"tool.py"}'}, "extra": {"function_id": "fresh-read"}},
            {"role": "function", "content": json.dumps({
                "status": "OK", "path": "tool.py", "code": "CURRENT = 2",
                "executor_state": {"phase": "candidate_verified", "current_candidate": 1,
                                    "remaining_tool_calls": 6, "next_action": "review_verification_and_submit_new_candidate_or_stop"},
            }), "extra": {"function_id": "fresh-read"}},
        ]
        wire = to_ollama_messages(compact_messages_for_budget(messages))
        payload = json.dumps(wire, ensure_ascii=False)
        self.assertIn('fresh-read', payload)
        self.assertIn('CURRENT = 2', payload)
        self.assertIn('remaining_tool_calls', payload)
        self.assertIn('return_leak', payload)
        ids = [call['id'] for item in wire for call in item.get('tool_calls', [])]
        results = [item.get('tool_call_id') for item in wire if item.get('role') == 'tool']
        self.assertEqual(ids, results)

    def test_compaction_does_not_keep_rejected_submit_as_current_candidate(self):
        messages = [
            {"role": "system", "content": "system"}, {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "function_call": {"name": "submit_patch", "arguments": "{\"code\":\"bad\"}"}, "extra": {"function_id": "s"}},
            {"role": "function", "content": json.dumps({"status": "REJECTED", "reason": "NO_CHANGE"}), "extra": {"function_id": "s"}},
        ]
        wire = to_ollama_messages(compact_messages_for_budget(messages))
        self.assertIn('\\"status\\": \\"REJECTED\\"', json.dumps(wire))
        self.assertIn('\\"reason\\": \\"NO_CHANGE\\"', json.dumps(wire))

    def test_rejected_verify_does_not_drop_latest_rules_evidence(self):
        messages = [
            {"role": "system", "content": "system"}, {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "function_call": {"name": "get_evidence", "arguments": "{}"}, "extra": {"function_id": "e"}},
            {"role": "function", "content": json.dumps({"status": "OK", "readable_paths": ["tool.py"], "required_checks": {"business": True}}), "extra": {"function_id": "e"}},
            {"role": "assistant", "content": "", "function_call": {"name": "verify_patch", "arguments": "{}"}, "extra": {"function_id": "v"}},
            {"role": "function", "content": json.dumps({"status": "REJECTED", "reason": "NO_ACCEPTED_CANDIDATE"}), "extra": {"function_id": "v"}},
        ]
        payload = json.dumps(to_ollama_messages(compact_messages_for_budget(messages)))
        self.assertIn('readable_paths', payload)
        self.assertIn('NO_ACCEPTED_CANDIDATE', payload)

    def test_executor_state_stop_conditions_are_in_worker(self):
        text = SOURCE.read_text(encoding="utf-8")
        self.assertIn("program_auto_verify", text)
        self.assertIn("candidate_already_verified", text)
        self.assertIn("NO_CHANGE", text)
        self.assertIn("STOPPED_TOOL_BUDGET", text)
        self.assertIn("no_progress_same_read", text)
        self.assertIn("STOPPED_NO_PROGRESS", text)
        self.assertIn("repeated_read_count", text)
        self.assertIn("last_read_sha256", text)
        self.assertIn("remaining_tool_calls", text)


if __name__ == "__main__":
    unittest.main()
