"""Derived CI formats (contract docs/integration/CONTRACT.md §3.1-3.3).

Fixtures are trimmed real reports from the Linux container prototype (b07
vulnerable/reference, b01 log leak, b05 forbidden read, default-Docker
UNKNOWN) plus two synthetic UNKNOWN shapes taken from project._verdict.
Each fixture deliberately carries absolute paths, a user-like path and a
credential-like value that must never reach a derived format.
"""
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock
import xml.etree.ElementTree as ET

from credproof_safety import cli
from credproof_safety.report_formats import (CONDITION_KEYS, ENVIRONMENT_UNAVAILABLE, EVIDENCE_INCOMPLETE, Context,
                                             report_sha256, to_junit, to_sarif, to_summary)

DATA = Path(__file__).resolve().parent / "data"
ROOT = Path(__file__).resolve().parents[2]
CONTEXT = Context(config_path="examples/bench/b07-webhook-relay/project/credproof.toml",
                  entry_path="examples/bench/b07-webhook-relay/project/tool.py", version="0.0.test")
FORBIDDEN_TEXT = ("CP_LAB_", "/home/", "/opt/", "/tmp/", "alice", "127.0.0.1", "bwrap", "\\")


def fixture(name):
    return json.loads((DATA / "report-formats" / f"{name}.json").read_text(encoding="utf-8"))


ALL = ("pass_b07", "pass_minimal", "fail_b07", "fail_b01", "fail_b05", "unknown_b07", "blocked", "not_reached")


class SarifTests(unittest.TestCase):
    def test_every_fixture_validates_against_official_schema(self):
        try:
            import jsonschema
        except ImportError:
            if os.environ.get("CREDPROOF_REQUIRE_SARIF_SCHEMA") == "1":
                self.fail("CREDPROOF_REQUIRE_SARIF_SCHEMA=1 but jsonschema is not installed (pip install .[test])")
            self.skipTest("jsonschema not installed; install the [test] extra to run the SARIF schema check")
        schema = json.loads((DATA / "sarif-schema-2.1.0.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft4Validator(schema)
        for name in ALL:
            with self.subTest(name):
                errors = sorted(validator.iter_errors(to_sarif(fixture(name), CONTEXT)), key=str)
                self.assertEqual(errors, [])

    def test_pass_has_no_results_and_successful_invocation(self):
        run = to_sarif(fixture("pass_b07"), CONTEXT)["runs"][0]
        self.assertEqual(run["results"], [])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])
        self.assertEqual(len(run["tool"]["driver"]["rules"]), 16)
        self.assertEqual(run["automationDetails"]["id"], f"credproof/{CONTEXT.config_path}/")

    def test_b07_fail_lists_the_three_violated_conditions_with_facts(self):
        run = to_sarif(fixture("fail_b07"), CONTEXT)["runs"][0]
        rules = [r["ruleId"] for r in run["results"]]
        self.assertEqual(rules, ["credproof/required_entry_scenarios", "credproof/no_forbidden_service_receipt",
                                 "credproof/no_unauthorized_connection"])
        texts = {r["ruleId"]: r["message"]["text"] for r in run["results"]}
        self.assertEqual(texts["credproof/no_forbidden_service_receipt"], "禁止的服务收到 1 次请求，其中 1 次携带了认证凭据。")
        self.assertEqual(texts["credproof/required_entry_scenarios"],
                         "场景结果不符：“allowed_service_redirect_refused”预期抛出 HTTPError，实际正常返回。")
        for result in run["results"]:
            location = result["locations"][0]["physicalLocation"]
            self.assertEqual(location["artifactLocation"], {"uri": CONTEXT.entry_path, "uriBaseId": "%SRCROOT%"})
            self.assertNotIn("region", location)  # runtime facts have no real line number
            self.assertEqual(result["level"], "error")
            self.assertEqual(run["tool"]["driver"]["rules"][result["ruleIndex"]]["id"], result["ruleId"])
        self.assertTrue(run["invocations"][0]["executionSuccessful"])

    def test_leak_and_forbidden_read_facts(self):
        b01 = {r["ruleId"]: r["message"]["text"] for r in to_sarif(fixture("fail_b01"), CONTEXT)["runs"][0]["results"]}
        self.assertEqual(list(b01), ["credproof/no_credential_output"])
        self.assertEqual(b01["credproof/no_credential_output"], "本次合成凭据出现在：日志。")
        b05 = {r["ruleId"]: r["message"]["text"] for r in to_sarif(fixture("fail_b05"), CONTEXT)["runs"][0]["results"]}
        self.assertIn("credproof/no_forbidden_file_read", b05)
        self.assertRegex(b05["credproof/no_forbidden_file_read"], r"^观测到对禁止目录中文件的访问尝试 \d+ 次。$")
        self.assertEqual(b05["credproof/required_pytest_tests"],
                         "必要测试用例 3 个：执行 3，通过 2，失败 1，跳过 0；未满足 1 个。")
        self.assertIn("返回值", b05["credproof/no_credential_output"])

    def test_unknown_kinds(self):
        for name, rule in (("unknown_b07", EVIDENCE_INCOMPLETE), ("blocked", ENVIRONMENT_UNAVAILABLE),
                           ("not_reached", EVIDENCE_INCOMPLETE)):
            with self.subTest(name):
                run = to_sarif(fixture(name), CONTEXT)["runs"][0]
                self.assertEqual([r["ruleId"] for r in run["results"]], [rule])
                self.assertFalse(run["invocations"][0]["executionSuccessful"])
        text = to_sarif(fixture("not_reached"), CONTEXT)["runs"][0]["results"][0]["message"]["text"]
        self.assertIn("redirect_blocked", text)

    def test_optional_cases_are_not_counted_as_required(self):
        report = fixture("fail_b05")
        observation = report["execution"]["pytest_observation"]
        observation["cases"]["tests/test_optional.py::test_extra"] = {
            "required": False, "collected": 1, "executed": 0, "passed": 0, "failed": 0, "skipped": 1}
        observation["required_paths"]["tests"]["skipped"] += 1
        texts = {r["ruleId"]: r["message"]["text"] for r in to_sarif(report, CONTEXT)["runs"][0]["results"]}
        self.assertIn("跳过 0", texts["credproof/required_pytest_tests"])

    def test_duration_keeps_recorded_float_and_drops_invalid(self):
        report = fixture("fail_b07")
        self.assertIsInstance(report["duration_ms"], float)
        result = to_sarif(report, CONTEXT)["runs"][0]["results"][0]
        self.assertEqual(result["properties"]["duration_ms"], report["duration_ms"])
        for bad in (-1, float("nan"), float("inf"), "12", True):
            report["duration_ms"] = bad
            with self.subTest(bad=bad):
                self.assertIsNone(to_sarif(report, CONTEXT)["runs"][0]["results"][0]["properties"]["duration_ms"])

    def test_fingerprint_is_stable_and_scoped_to_config(self):
        a = to_sarif(fixture("fail_b07"), CONTEXT)["runs"][0]["results"][0]["partialFingerprints"]
        b = to_sarif(fixture("fail_b07"), CONTEXT)["runs"][0]["results"][0]["partialFingerprints"]
        other = Context(config_path="other/credproof.toml", entry_path="other/tool.py", version="0.0.test")
        c = to_sarif(fixture("fail_b07"), other)["runs"][0]["results"][0]["partialFingerprints"]
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_report_digest_is_canonical(self):
        report = fixture("fail_b07")
        reordered = json.loads(json.dumps(report, sort_keys=False))
        self.assertEqual(report_sha256(report), report_sha256(dict(reversed(list(reordered.items())))))


class JunitAndSummaryTests(unittest.TestCase):
    def counts(self, name):
        suite = ET.fromstring(to_junit(fixture(name), CONTEXT))
        return suite, int(suite.get("tests")), int(suite.get("failures")), int(suite.get("errors"))

    def test_junit_shapes(self):
        _, tests, failures, errors = self.counts("pass_b07")
        self.assertEqual((tests, failures, errors), (14, 0, 0))
        suite, tests, failures, errors = self.counts("fail_b07")
        self.assertEqual((tests, failures, errors), (14, 3, 0))
        failed = [case.get("name").split()[0] for case in suite.iter("testcase") if case.find("failure") is not None]
        self.assertEqual(failed, ["required_entry_scenarios", "no_forbidden_service_receipt", "no_unauthorized_connection"])
        suite, tests, failures, errors = self.counts("unknown_b07")
        self.assertEqual((tests, failures, errors), (1, 0, 1))
        self.assertEqual(next(suite.iter("testcase")).get("name"), "evidence_complete")
        self.assertEqual(len(CONDITION_KEYS), 14)

    def test_summary_lists_facts_and_reproduction(self):
        text = to_summary(fixture("fail_b07"), CONTEXT)
        self.assertIn("CredProof 验收：不通过", text)
        self.assertIn("禁止的服务收到 1 次请求，其中 1 次携带了认证凭据。", text)
        self.assertIn(f"credproof-safety check --config {CONTEXT.config_path}", text)
        self.assertIn("证据不足按安全失败处理", to_summary(fixture("unknown_b07"), CONTEXT))

    def test_pass_summary_claims_only_what_the_record_shows(self):
        full = to_summary(fixture("pass_b07"), CONTEXT)
        self.assertIn("本配置声明的 14 项条件全部满足。", full)
        self.assertIn("观测到对允许目录中资料的访问。", full)
        self.assertIn("观测到携带正确凭据访问允许的服务。", full)
        minimal = to_summary(fixture("pass_minimal"), CONTEXT)
        self.assertIn("本配置声明的 14 项条件全部满足。", minimal)
        for claim in ("允许目录中资料", "凭据访问", "允许服务的请求", "实际读取", "完成授权认证"):
            self.assertNotIn(claim, minimal)

    def test_no_credential_path_or_user_reaches_any_format(self):
        for name in ALL:
            report = fixture(name)
            outputs = (json.dumps(to_sarif(report, CONTEXT), ensure_ascii=False), to_junit(report, CONTEXT),
                       to_summary(report, CONTEXT))
            for output in outputs:
                for marker in FORBIDDEN_TEXT:
                    with self.subTest(name=name, marker=marker):
                        self.assertNotIn(marker, output)

    def test_context_rejects_unsafe_paths(self):
        for bad in ("/abs/credproof.toml", "../x/credproof.toml", "a\\b.toml", "C:/x.toml", ""):
            with self.subTest(bad), self.assertRaises(ValueError):
                Context(config_path=bad, entry_path="tool.py", version="x")


class CliTests(unittest.TestCase):
    def test_usage_errors_exit_4_and_help_exits_0(self):
        for argv, code in ((["check"], 4), (["check", "--config", "x", "--bogus"], 4), (["nosuch"], 4), ([], 4),
                           (["--help"], 0), (["check", "--help"], 0)):
            with self.subTest(argv), mock.patch("sys.stderr", io.StringIO()), mock.patch("sys.stdout", io.StringIO()), \
                    self.assertRaises(SystemExit) as raised:
                cli.main(argv)
            self.assertEqual(raised.exception.code, code)

    def project(self, tmp):
        source = Path(tmp) / "repo"
        shutil.copytree(ROOT / "examples/bench/b07-webhook-relay/project", source / "svc" / "relay")
        return source, source / "svc" / "relay" / "credproof.toml"

    def test_check_writes_derived_formats_and_keeps_exit_codes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, config = self.project(tmp)
            out = Path(tmp) / "out"
            for name, code in (("fail_b07", 2), ("pass_b07", 0), ("unknown_b07", 3)):
                with self.subTest(name), mock.patch.object(cli, "check_project", return_value=fixture(name)), \
                        mock.patch("sys.stdout", io.StringIO()):
                    rc = cli.main(["check", "--config", str(config), "--source-root", str(source),
                                   "--sarif", str(out / f"{name}.sarif"), "--junit", str(out / f"{name}.xml"),
                                   "--summary", str(out / f"{name}.md")])
                self.assertEqual(rc, code)
                sarif = json.loads((out / f"{name}.sarif").read_text(encoding="utf-8"))
                run = sarif["runs"][0]
                self.assertEqual(run["automationDetails"]["id"], "credproof/svc/relay/credproof.toml/")
                for result in run["results"]:
                    self.assertEqual(result["locations"][0]["physicalLocation"]["artifactLocation"]["uri"], "svc/relay/tool.py")
                self.assertTrue((out / f"{name}.xml").is_file() and (out / f"{name}.md").is_file())

    def test_config_outside_source_root_is_an_error_before_checking(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, config = self.project(tmp)
            elsewhere = Path(tmp) / "elsewhere"
            elsewhere.mkdir()
            with mock.patch.object(cli, "check_project") as check, mock.patch("sys.stderr", io.StringIO()):
                rc = cli.main(["check", "--config", str(config), "--source-root", str(elsewhere),
                               "--sarif", str(Path(tmp) / "x.sarif")])
            self.assertEqual(rc, 4)
            check.assert_not_called()

    def test_plain_check_does_not_need_source_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, config = self.project(tmp)
            with mock.patch.object(cli, "check_project", return_value=fixture("pass_b07")), \
                    mock.patch("sys.stdout", io.StringIO()):
                self.assertEqual(cli.main(["check", "--config", str(config)]), 0)


if __name__ == "__main__":
    unittest.main()
