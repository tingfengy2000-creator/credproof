"""Independent mechanism checks on disposable repositories and synthetic markers.

These tests are engineering checks, not a held-out evaluation dataset. They use
the actual pinned Gitleaks binary and never authenticate a credential. Set
CREDPROOF_GITLEAKS to its path when running on another machine.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from credproof import core
from credproof.scanner import Gitleaks


PROJECT = Path(__file__).resolve().parents[1]
MARKER_A = "CP_SYNTH_" + "A1" * 12
MARKER_B = "CP_SYNTH_" + "B2" * 12


def fixture(marker=MARKER_A, extra=""):
    # The non-ASCII comment and CRLF exercise byte preservation around the edit.
    return (
        "# 独立合成夹具；不能用于任何实际认证\r\n"
        "import os\r\n"
        f'SERVICE_TOKEN = "{marker}"\r\n'
        "TIMEOUT = 15\r\n"
        "\r\n"
        "def authorization_header():\r\n"
        '    return "Bearer " + SERVICE_TOKEN\r\n'
        + extra
    ).encode("utf-8")


class CoreMechanismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("CREDPROOF_GITLEAKS")
        executable = Path(configured) if configured else (
            PROJECT / ".tools" / "gitleaks-8.28.0" / "gitleaks.exe"
        )
        if not executable.is_file():
            raise unittest.SkipTest(
                "Pinned real Gitleaks 8.28.0 not available; set CREDPROOF_GITLEAKS. "
                "These checks are not replaced by a mock scanner."
            )
        if shutil.which("git") is None:
            raise unittest.SkipTest("Git is required for real index/worktree checks")
        cls.executable = executable
        cls.rules = PROJECT / "config" / "synthetic-gitleaks.toml"
        cls.scanner = Gitleaks(executable, cls.rules)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="credproof-independent-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.serial = 0

    def git(self, repo, *arguments):
        env = {
            key: value for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                   GIT_OPTIONAL_LOCKS="0")
        return subprocess.run(
            ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=",
             "-C", str(repo), *arguments],
            capture_output=True, check=True, timeout=10, env=env,
        ).stdout

    def repository(self, marker=MARKER_A, extra=""):
        self.serial += 1
        repo = self.root / f"repo-{self.serial}"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        self.git(repo, "config", "core.autocrlf", "false")
        (repo / "config.py").write_bytes(fixture(marker, extra))
        (repo / "notes.txt").write_bytes(b"A deliberately unchanged companion file.\n")
        self.git(repo, "add", "--", "config.py", "notes.txt")
        return repo

    def freeze(self, repo, *, source="index", allow_fixture=True, scanner=None):
        self.serial += 1
        bundle = self.root / f"bundle-{self.serial}"
        core.freeze(repo, bundle, scanner or self.scanner, source=source,
                    allow_fixture=allow_fixture)
        return bundle

    @staticmethod
    def original_bytes(repo):
        # No status command or scanner-derived oracle is used for this assertion.
        return {
            "config.py": (repo / "config.py").read_bytes(),
            "notes.txt": (repo / "notes.txt").read_bytes(),
            "index": (repo / ".git" / "index").read_bytes(),
        }

    def assert_public_report_redacted(self, report):
        public = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(MARKER_A, public)
        self.assertNotIn(MARKER_B, public)
        self.assertNotIn("target_value", public)
        self.assertNotIn("hmac_key", public)

    def test_planned_edit_passes_without_modifying_originals(self):
        repo = self.repository()
        originals = self.original_bytes(repo)
        bundle = self.freeze(repo)
        actual = (bundle / "candidate" / "config.py").read_bytes()
        expected = originals["config.py"].replace(
            f'"{MARKER_A}"'.encode(), b'os.environ["CP_DEMO_TOKEN"]', 1
        )
        self.assertEqual(expected, actual)
        self.assertNotEqual(originals["config.py"], actual)

        report = core.recheck(bundle, self.scanner)
        self.assertEqual("PASS", report["verdict"])
        self.assertEqual("PASS", report["obligations"]["allowed_changes"]["status"])
        self.assertEqual(originals, self.original_bytes(repo))
        self.assertEqual("PRESENT", report["remaining_risks"]["index"]["presence"])
        self.assertEqual("NOT_SCANNED", report["remaining_risks"]["history"])
        self.assertEqual("UNKNOWN", report["remaining_risks"]["external_revocation"])
        self.assert_public_report_redacted(report)

    def test_index_and_worktree_capture_different_real_content(self):
        repo = self.repository(MARKER_A)
        (repo / "config.py").write_bytes(fixture(MARKER_B))
        originals = self.original_bytes(repo)
        index_bundle = self.freeze(repo, source="index")
        worktree_bundle = self.freeze(repo, source="worktree")

        self.assertEqual(fixture(MARKER_A), (index_bundle / "before" / "config.py").read_bytes())
        self.assertEqual(fixture(MARKER_B), (worktree_bundle / "before" / "config.py").read_bytes())
        report = core.recheck(index_bundle, self.scanner)
        self.assertEqual("PASS", report["verdict"])
        self.assertEqual("PRESENT", report["remaining_risks"]["index"]["presence"])
        self.assertEqual("ABSENT_WITHIN_SCOPE", report["remaining_risks"]["worktree"]["presence"])
        self.assertEqual(originals, self.original_bytes(repo))
        self.assert_public_report_redacted(report)

    def test_extra_change_invalidates_old_evidence_and_fresh_check_fails(self):
        repo = self.repository()
        bundle = self.freeze(repo)
        evidence = core.collect(bundle, self.scanner)
        self.assertEqual("PASS", core.assess(bundle, evidence, self.scanner)["verdict"])
        path = bundle / "candidate" / "config.py"
        data = path.read_bytes()
        self.assertIn(b"TIMEOUT = 15", data)
        path.write_bytes(data.replace(b"TIMEOUT = 15", b"TIMEOUT = 99"))

        old_report = core.assess(bundle, evidence, self.scanner)
        self.assertEqual("UNKNOWN", old_report["verdict"])
        fresh_report = core.recheck(bundle, self.scanner)
        self.assertEqual("FAIL", fresh_report["verdict"])
        self.assertEqual("PASS", fresh_report["obligations"]["scan"]["status"])
        self.assertEqual("PASS", fresh_report["obligations"]["function"]["status"])
        self.assertEqual("FAIL", fresh_report["obligations"]["allowed_changes"]["status"])

    def test_scope_rules_and_cross_contract_receipts_are_not_interchangeable(self):
        repo = self.repository()
        bundle = self.freeze(repo)
        evidence = core.collect(bundle, self.scanner)
        with self.subTest("scope was narrowed before receipt collection"):
            narrowed = core.collect(bundle, self.scanner, scope_override=("config.py",))
            self.assertEqual("UNKNOWN", core.assess(bundle, narrowed, self.scanner)["verdict"])

        with self.subTest("borrowed scan receipt despite identical candidate bytes"):
            other_repo = self.repository(MARKER_B)
            other_bundle = self.freeze(other_repo)
            other = core.collect(other_bundle, self.scanner)
            self.assertEqual(evidence["candidate_manifest"], other["candidate_manifest"])
            mixed = copy.deepcopy(evidence)
            mixed["checks"]["scan"] = other["checks"]["scan"]
            self.assertEqual("UNKNOWN", core.assess(bundle, mixed, self.scanner)["verdict"])

        with self.subTest("even a version-only rules change requires new evidence"):
            rules = self.root / "private-rules.toml"
            rules.write_bytes(self.rules.read_bytes())
            scanner = Gitleaks(self.executable, rules)
            rules_bundle = self.freeze(repo, scanner=scanner)
            old = core.collect(rules_bundle, scanner)
            rules.write_bytes(rules.read_bytes() + b"\n# new configuration revision\n")
            self.assertEqual("UNKNOWN", core.assess(rules_bundle, old, scanner)["verdict"])
            self.assertEqual("UNKNOWN", core.recheck(rules_bundle, scanner)["verdict"])

    def test_missing_required_obligation_cannot_become_pass(self):
        bundle = self.freeze(self.repository())
        evidence = core.collect(bundle, self.scanner)
        self.assertEqual("PASS", evidence["checks"]["function"]["status"])
        del evidence["checks"]["function"]
        report = core.assess(bundle, evidence, self.scanner)
        self.assertEqual("UNKNOWN", report["verdict"])
        self.assertEqual("UNKNOWN", report["obligations"]["function"]["status"])

    def test_recheck_ignores_deleted_or_forged_saved_verdicts(self):
        bundle = self.freeze(self.repository())
        for name in ("report.json", "evidence.json"):
            (bundle / name).write_text('{"verdict":"FAIL"}', encoding="utf-8")
        self.assertEqual("PASS", core.recheck(bundle, self.scanner)["verdict"])
        for name in ("report.json", "evidence.json"):
            (bundle / name).unlink()
        self.assertEqual("PASS", core.recheck(bundle, self.scanner)["verdict"])

        (bundle / "candidate" / "notes.txt").write_text(
            "The second file was changed outside the plan.\n", encoding="utf-8"
        )
        for name in ("report.json", "evidence.json"):
            (bundle / name).write_text(
                '{"verdict":"PASS","checks":{"scan":{"status":"PASS"}}}',
                encoding="utf-8",
            )
        self.assertEqual("FAIL", core.recheck(bundle, self.scanner)["verdict"])

    def test_unknown_function_profile_and_hostile_file_are_never_executed(self):
        with self.subTest("no functional authorization"):
            bundle = self.freeze(self.repository(), allow_fixture=False)
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("UNKNOWN", report["verdict"])
            self.assertEqual("UNKNOWN", report["obligations"]["function"]["status"])

        with self.subTest("arbitrary top-level open is not fixture execution"):
            sentinel = self.root / "unexpected-side-effect.txt"
            code = f"open({str(sentinel)!r}, 'w').write('MUST NOT RUN')\r\n"
            bundle = self.freeze(self.repository(extra=code))
            self.assertFalse(sentinel.exists())
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("UNKNOWN", report["verdict"])
            self.assertEqual("UNKNOWN", report["obligations"]["function"]["status"])
            self.assertFalse(sentinel.exists(), "Verifier executed arbitrary repository code")

    def test_missing_before_and_linked_candidate_material_are_rejected(self):
        with self.subTest("before material cannot be replaced by a saved PASS"):
            bundle = self.freeze(self.repository())
            (bundle / "before" / "config.py").unlink()
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("UNKNOWN", report["verdict"])

        with self.subTest("candidate may not escape through a link"):
            bundle = self.freeze(self.repository())
            outside = self.root / "outside.txt"
            outside.write_text("Outside the declared candidate.\n", encoding="utf-8")
            link = bundle / "candidate" / "notes.txt"
            link.unlink()
            try:
                link.symlink_to(outside)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f"Host cannot create the link fixture: {type(error).__name__}")
            before = outside.read_bytes()
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("UNKNOWN", report["verdict"])
            self.assertEqual(before, outside.read_bytes())

    def test_decoded_residual_and_comment_residual_fail_without_public_plaintext(self):
        with self.subTest("escaped literal passes regex but fails independent removal"):
            bundle = self.freeze(self.repository())
            path = bundle / "candidate" / "config.py"
            escaped = "".join(f"\\x{ord(char):02x}" for char in MARKER_A)
            path.write_bytes(path.read_bytes() + f'LEAK = "{escaped}"\r\n'.encode())
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("PASS", report["obligations"]["scan"]["status"])
            self.assertEqual("FAIL", report["obligations"]["removal"]["status"])
            self.assertEqual("FAIL", report["verdict"])
            self.assert_public_report_redacted(report)

        with self.subTest("comment still exposes the full value"):
            bundle = self.freeze(self.repository())
            (bundle / "candidate" / "notes.txt").write_text(
                "# example " + MARKER_A + "\n", encoding="utf-8"
            )
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("FAIL", report["obligations"]["removal"]["status"])
            self.assertEqual("FAIL", report["verdict"])
            self.assert_public_report_redacted(report)

        with self.subTest("public path metadata may not reveal the target value"):
            repo = self.repository()
            sensitive_name = f"note-{MARKER_A}.txt"
            (repo / sensitive_name).write_text("Ordinary companion content.\n", encoding="utf-8")
            self.git(repo, "add", "--", sensitive_name)
            bundle = self.root / "bundle-sensitive-path"
            core.freeze(repo, bundle, self.scanner, scope=("config.py", sensitive_name),
                        allow_fixture=True)
            evidence = core.collect(bundle, self.scanner)
            self.assert_public_report_redacted(evidence)
            assessed = core.assess(bundle, evidence, self.scanner)
            self.assertEqual("PASS", assessed["verdict"])
            self.assert_public_report_redacted(assessed)
            report = core.recheck(bundle, self.scanner)
            self.assertEqual("PASS", report["verdict"])
            self.assert_public_report_redacted(report)

    def test_current_source_change_is_reported_without_overriding_local_acceptance(self):
        repo = self.repository()
        bundle = self.freeze(repo)
        # External maintenance is distinct from verifier side effects. The
        # acceptance object remains the fixed before/candidate, not current HEAD.
        (repo / "config.py").write_bytes(fixture(MARKER_B))
        self.git(repo, "add", "--", "config.py")
        externally_updated = self.original_bytes(repo)

        report = core.recheck(bundle, self.scanner)
        self.assertEqual("PASS", report["verdict"])
        for layer in ("worktree", "index"):
            current = report["remaining_risks"][layer]
            self.assertFalse(current["unchanged_since_freeze"])
            self.assertFalse(current["matches_candidate"])
            self.assertEqual("ABSENT_WITHIN_SCOPE", current["presence"])
        self.assertEqual(externally_updated, self.original_bytes(repo))
        self.assert_public_report_redacted(report)


if __name__ == "__main__":
    unittest.main()
