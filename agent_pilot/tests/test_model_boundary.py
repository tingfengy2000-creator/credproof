"""Static contract checks for the model-process boundary launcher.

These tests do not stand in for the real WSL run.  The public acceptance record
contains the fresh boundary probe and the finite model trace; this file guards
against accidentally reverting to the old whole-checkout launcher.
"""
from pathlib import Path
import unittest

from credproof_safety.agent import _model_feedback, _phase_rejection
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


if __name__ == "__main__":
    unittest.main()
