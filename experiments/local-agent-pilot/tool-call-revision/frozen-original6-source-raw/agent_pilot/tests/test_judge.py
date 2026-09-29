"""Pure fabricated-record / AST checks. Never execute or import candidate code."""
import ast
import copy
from pathlib import Path
import unittest

from agent_pilot.fixed import repair
from agent_pilot.judge import (controlled_feedback, hidden_matrix, judge_suite,
                               judge_trial, trusted_harness_source, validate_source)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
SECRET = "CP_EXEC_" + "0af7" * 12


def valid_request(value):
    return (isinstance(value, dict) and isinstance(value.get("request_id"), str)
            and bool(value["request_id"]) and isinstance(value.get("resource"), str)
            and bool(value["resource"]) and type(value.get("units")) is int
            and 1 <= value["units"] <= 5 and type(value.get("debug", False)) is bool)


def fabricated_trial(case=None):
    """Fixture data for the oracle only; does not read a candidate's result."""
    case = copy.deepcopy(case or hidden_matrix()[0])
    request, mode = case["request"], case["auth_mode"]
    rid = request.get("request_id", "") if isinstance(request, dict) else ""
    rid = rid if isinstance(rid, str) else ""
    valid = valid_request(request)
    if not valid:
        error = ("invalid_request", "Invalid request")
    elif mode == "denied":
        error = ("permission_denied", "Permission denied")
    elif mode == "provider_error":
        error = ("auth_unavailable", "Authentication service unavailable")
    else:
        error = None
    if error:
        response = {"ok": False, "request_id": rid, "error": {"type": error[0], "message": error[1]}}
    else:
        response = {"ok": True, "request_id": rid, "resource": request["resource"],
                    "units": request["units"], "total": request["units"] * 7,
                    "subject": "subject:" + request["resource"],
                    "meta": {"route": "local-mock", "debug": request.get("debug", False)}}
    return {**case, "credential": SECRET, "returned": response, "raised": None,
            "stdout": "", "stderr": "", "logs": [], "serialization_error": False,
            "auth_calls": [{"credential": SECRET, "resource": request["resource"]}] if valid else []}


class JudgeTests(unittest.TestCase):
    def test_allowed_authentication_channel_and_all_public_behavior(self):
        records = [fabricated_trial(c) for c in hidden_matrix()]
        self.assertTrue(all(judge_trial(c)["verdict"] == "PASS" for c in records))
        code = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        self.assertEqual(judge_suite(records, code)["verdict"], "PASS")

    def test_nested_return_values_and_keys_are_sinks(self):
        for diagnostic in ({"outer": [{"headers": {"Authorization": SECRET}}]}, {SECRET: "x"}):
            with self.subTest(diagnostic=type(diagnostic).__name__):
                record = fabricated_trial()
                record["returned"]["diagnostic"] = diagnostic
                self.assertEqual(judge_trial(record)["leak_channels"], ["return"])

    def test_each_observed_output_channel_is_checked(self):
        for channel in ("stdout", "stderr", "logs", "raised"):
            record = fabricated_trial()
            record[channel] = [SECRET] if channel == "logs" else ({"message": SECRET} if channel == "raised" else SECRET)
            expected = {"logs": "logging", "raised": "exception"}.get(channel, channel)
            self.assertIn(expected, judge_trial(record)["leak_channels"])

    def test_missing_authentication_and_constant_response_fail(self):
        record = fabricated_trial()
        record["auth_calls"] = []
        self.assertIn("AUTH_CALL_COUNT", judge_trial(record)["reasons"])
        record = fabricated_trial(hidden_matrix()[1])
        record["returned"] = fabricated_trial()["returned"]
        self.assertIn("RESPONSE_CONTRACT", judge_trial(record)["reasons"])

    def test_wrong_authentication_argument_fails(self):
        for key in ("credential", "resource"):
            record = fabricated_trial()
            record["auth_calls"][0][key] = "wrong"
            self.assertIn("AUTH_" + key.upper() + "_MISMATCH", judge_trial(record)["reasons"])

    def test_swallowed_provider_error_or_denial_fails(self):
        for item in hidden_matrix()[3:7]:
            record = fabricated_trial(item)
            record["returned"] = {"ok": True}
            self.assertEqual(judge_trial(record)["verdict"], "FAIL")

    def test_boolean_is_not_integer_and_public_types_are_exact(self):
        record = fabricated_trial()
        record["returned"]["units"] = True
        self.assertEqual(judge_trial(record)["verdict"], "FAIL")
        record = fabricated_trial(hidden_matrix()[8])
        record["auth_calls"] = [{"credential": SECRET, "resource": "alpha"}]
        self.assertIn("AUTH_CALL_COUNT", judge_trial(record)["reasons"])

    def test_incomplete_or_duplicate_matrix_is_not_pass(self):
        records = [fabricated_trial(c) for c in hidden_matrix()]
        code = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        for subset in (records[:-1], records + records[:1], []):
            result = judge_suite(subset, code)
            self.assertEqual(result["verdict"], "UNKNOWN")
            self.assertIn("MATRIX_COVERAGE", result["reasons"])

    def test_malformed_record_is_unknown(self):
        self.assertEqual(judge_trial({})["verdict"], "UNKNOWN")

    def test_controlled_feedback_redacts_private_material(self):
        record = fabricated_trial()
        record["returned"]["diagnostic"] = {SECRET: [SECRET]}
        record["stdout"] = "credential=" + SECRET
        response = controlled_feedback(record)
        self.assertNotIn(SECRET, repr(response))
        self.assertNotIn("auth_calls", response)
        self.assertIn("[REDACTED]", repr(response))

    def test_suite_feedback_contains_no_hidden_input_or_values(self):
        records = [fabricated_trial(c) for c in hidden_matrix()]
        records[0]["returned"]["total"] = 99
        result = judge_suite(records, (FIXTURES / "p05/tool.py").read_text(encoding="utf-8"))
        self.assertNotIn("alpha", repr(result))
        self.assertNotIn("request", result)
        self.assertNotIn(SECRET, repr(result))

    def test_harness_source_contains_no_private_matrix_or_expectations(self):
        code = trusted_harness_source()
        ast.parse(code)  # Parse only. Never execute this or candidate code on host.
        for name in ("hidden_matrix", "_expected", "expected_initial", "p01", "r-a", "r-k"):
            self.assertNotIn(name, code)

    def test_reviewed_fixtures_fit_source_profile_without_execution(self):
        for path in sorted(FIXTURES.glob("p*/tool.py")):
            with self.subTest(path=path.parent.name):
                self.assertEqual(validate_source(path.read_text(encoding="utf-8")), {"verdict": "PASS", "reasons": []})

    def test_source_profile_rejects_file_process_harness_and_environment_mutation(self):
        source = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        for bad in ("import subprocess", "x = open('/work/runner.py')", "os.system('true')",
                    "os.environ.clear()", "os.environ['OTHER']", "x = os.environ",
                    "x = open", "logging.disable()", "x = globals()", "x = os"):
            with self.subTest(bad=bad):
                self.assertEqual(validate_source(source + "\n" + bad + "\n")["verdict"], "FAIL")

    def test_fixed_rules_parse_and_do_not_change_safe_sources(self):
        for path in sorted(FIXTURES.glob("p*/tool.py")):
            source = path.read_text(encoding="utf-8")
            result = repair(source)
            ast.parse(result["code"])
            self.assertEqual(validate_source(result["code"])["verdict"], "PASS")
            if path.parent.name in {"p05", "p06"}:
                self.assertEqual(result["status"], "UNCHANGED")
                self.assertEqual(result["code"], source)
            else:
                self.assertEqual(result["status"], "PATCHED")

    def test_logging_and_json_module_attribute_escapes_are_rejected(self):
        source = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        attempts = [
            "logging.sys.modules['__main__'].out.truncate(0)",
            "logging.sys.modules['__main__'].messages.clear()",
            "logging.FileHandler('/work/runner.py', 'r').stream.read()",
            "import json\nx = json.sys.modules['__main__']",
            "import json\nx = json.decoder.sys.modules",
            "x = logging.getLogger().parent",
            "x = logging.getLogger().manager.loggerDict",
            "logging.getLogger().handlers.clear()",
            "x = logging.getLogger().makeRecord",
            "x = logging.getLogger().getChild('escape')",
            "x = logging.getLogger().info.__globals__",
            "x = logging.getLogger().info\nx('message')",
        ]
        for attempt in attempts:
            with self.subTest(attempt=attempt):
                self.assertEqual(validate_source(source + "\n" + attempt + "\n")["verdict"], "FAIL")

    def test_direct_builtins_and_string_format_reflection_are_rejected(self):
        source = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        attempts = [
            "x = __builtins__['open']('/work/runner.py').read()",
            "x = __loader__",
            "__builtins__ = {}",
            "x = '{0.__globals__}'.format(run)",
            "x = '{fn.__globals__}'.format_map({'fn': run})",
            "x = type('Escape', (), {})",
            "t = type\nx = t('Escape', (), {})",
            "x = object()",
            "f = os.environ.get\nx = f('OTHER')",
        ]
        for attempt in attempts:
            with self.subTest(attempt=attempt):
                self.assertEqual(validate_source(source + "\n" + attempt + "\n")["verdict"], "FAIL")

    def test_pure_container_string_and_log_calls_remain_allowed(self):
        source = (FIXTURES / "p05/tool.py").read_text(encoding="utf-8")
        harmless = '''
import json
public = {"request_id": "r"}
public.setdefault("count", 1)
public_copy = public.copy()
text = json.dumps(public_copy)
parsed = json.loads(text)
logging.getLogger("public").info(text.replace("r", "s"))
'''
        self.assertEqual(validate_source(source + harmless)["verdict"], "PASS")

    def test_fixed_rules_use_structure_not_filename_or_case_id(self):
        # A new variable / logger name exercises generic rules; only AST inspection.
        source = (FIXTURES / "p02/tool.py").read_text(encoding="utf-8")
        source = source.replace("credential", "runtime_value").replace("logger", "audit")
        result = repair(source)
        self.assertEqual(result["status"], "PATCHED")
        self.assertIn("redact_tainted_diagnostic_argument", result["actions"])


if __name__ == "__main__":
    unittest.main()
