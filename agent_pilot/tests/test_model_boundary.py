"""Static contract checks for the model-process boundary launcher.

These tests do not stand in for the real WSL run.  The public acceptance record
contains the fresh boundary probe and the finite model trace; this file guards
against accidentally reverting to the old whole-checkout launcher.
"""
from pathlib import Path
import json
import unittest

from credproof_safety.agent import _model_feedback, _model_initial_context, _phase_rejection
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

    def test_budget_compaction_keeps_latest_native_pair_only(self):
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "task"},
            {"role": "assistant", "content": "", "function_call": {"name": "get_evidence", "arguments": "{}"},
             "extra": {"function_id": "e"}},
            {"role": "function", "content": "full evidence", "extra": {"function_id": "e"}},
            {"role": "assistant", "content": "", "function_call": {"name": "submit_patch", "arguments": "{\"code\":\"x\"}"},
             "extra": {"function_id": "s"}},
            {"role": "function", "content": "accepted", "extra": {"function_id": "s"}},
            {"role": "assistant", "content": "", "function_call": {"name": "verify_patch", "arguments": "{}"},
             "extra": {"function_id": "v"}},
            {"role": "function", "content": "failure evidence", "extra": {"function_id": "v"}},
        ]
        compacted = compact_messages_for_budget(messages)
        self.assertEqual(len(compacted), 4)
        wire = to_ollama_messages(compacted)
        self.assertEqual([item["role"] for item in wire], ["system", "user", "assistant", "tool"])
        self.assertEqual(wire[-1]["tool_call_id"], "v")


if __name__ == "__main__":
    unittest.main()
