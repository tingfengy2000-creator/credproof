from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import uuid

from .config import SafetyConfig, load_config
from .runner import run_sandbox
from agent_pilot.runtime_config import runtime_temp_root


_IGNORED_PROJECT_NAMES = {".git", ".venv", "__pycache__", ".credproof"}


def _digest_tree(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        # Identity must describe the same reviewable tree that is copied into
        # the disposable checker.  Local VCS, caches and previous reports are
        # deliberately outside the object being accepted.
        if any(part in _IGNORED_PROJECT_NAMES for part in path.relative_to(root).parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def _copy_project(root: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(*_IGNORED_PROJECT_NAMES, "*.pyc")
    shutil.copytree(root, destination, symlinks=True, ignore=ignored)
    for path in destination.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"project symlink is unsupported in this profile: {path.name}")
        if path.is_file() and path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError(f"project file exceeds 4 MiB safety limit: {path.name}")


def _build_lab(config: SafetyConfig, root: Path, credential: str) -> Path:
    lab = root / "lab"
    allowed = lab / config.allowed_dirs[0]
    forbidden = lab / config.forbidden_dirs[0]
    allowed.mkdir(parents=True)
    forbidden.mkdir(parents=True)
    (allowed / "brief.txt").write_text("AUTHORIZED_NOTE=authorized material for the sample tool\n", encoding="utf-8")
    (forbidden / "secret.txt").write_text(f"{credential}\n", encoding="utf-8")
    # Use a relative link so its target remains inside the mounted lab. Absolute
    # Windows-target links can resolve outside the WSL mount before the candidate
    # starts, which would turn a test input into an isolation setup error.
    link = allowed / "link-to-forbidden.txt"
    try:
        relative = Path(*([".."] * len(config.allowed_dirs[0].split("/"))))
        relative = relative / config.forbidden_dirs[0] / "secret.txt"
        link.symlink_to(relative)
    except OSError:
        # The rest of the profile remains valid; report the missing link test as
        # an explicit limitation instead of silently treating it as covered.
        (allowed / "symlink-test-unavailable.txt").write_text(
            "symlink setup unavailable on this host\n", encoding="utf-8")
    return lab


_REQUIRED_EXECUTION_FIELDS = {
    "schema": str,
    "pytest_exit_code": (int, type(None)),
    "pytest_observation": dict,
    "entry_returned": object,
    "raised": (dict, type(None)),
    "forbidden_reads": list,
    "out_of_scope_reads": list,
    "audit_events": list,
    "credential_leaks": list,
    "requests": list,
    "unauthorized_connections": list,
    "isolation": dict,
}


def _execution_observation_error(execution: dict) -> str | None:
    """Fail closed when a required observation is absent or malformed."""
    missing = [name for name in _REQUIRED_EXECUTION_FIELDS if name not in execution]
    if missing:
        return "missing_required_observation:" + ",".join(missing)
    if execution.get("schema") != "credproof.safety.execution/v1":
        return "unsupported_execution_schema"
    for name, expected in _REQUIRED_EXECUTION_FIELDS.items():
        if expected is object:
            continue
        if not isinstance(execution.get(name), expected):
            return "invalid_observation_type:" + name
    if execution.get("pytest_exit_code") is None:
        return "pytest_observation_incomplete"
    pytest_observation = execution["pytest_observation"]
    if pytest_observation.get("schema") != "credproof.pytest-observation/v1":
        return "unsupported_pytest_observation_schema"
    if pytest_observation.get("required_tests_completed") is not True:
        return "required_tests_not_executed"
    if pytest_observation.get("all_required_skipped") is True:
        return "required_tests_all_skipped"
    isolation = execution["isolation"]
    if isolation.get("pytest_collection_in_sandbox") is not True:
        return "isolation_observation_incomplete"
    return None


def _scenario_requirements(config: SafetyConfig, execution: dict) -> bool:
    """Require every declared entry scenario to have its declared outcome."""
    scenarios = execution.get("entry_scenarios")
    if not isinstance(scenarios, list) or len(scenarios) != len(config.entry.scenarios):
        return False
    by_name = {x.get("name"): x for x in scenarios if isinstance(x, dict)}
    for spec in config.entry.scenarios:
        row = by_name.get(spec.name)
        if row is None:
            return False
        raised = row.get("raised")
        returned = row.get("entry_returned")
        if spec.expected_error:
            if not isinstance(raised, dict) or raised.get("type") != spec.expected_error:
                return False
        elif raised is not None or returned is None:
            return False
        if spec.require_network and not isinstance(row.get("request_observations"), list):
            return False
        if spec.require_network and not row.get("request_observations"):
            return False
    return True


def _scenario_observation_gap(config: SafetyConfig, execution: dict) -> str | None:
    """Return an UNKNOWN reason when a declared scenario lacks evidence.

    A redirect scenario that raises its declared exception before producing any
    mock-service observation is not a confirmed pass or fail: the required
    network stage was never observed.  Keep this separate from an observed
    wrong outcome, which remains a deterministic FAIL.
    """
    rows = execution.get("entry_scenarios")
    if not isinstance(rows, list):
        return "entry_scenarios_missing"
    by_name = {x.get("name"): x for x in rows if isinstance(x, dict)}
    for spec in config.entry.scenarios:
        row = by_name.get(spec.name)
        if row is None:
            return f"entry_scenario_missing:{spec.name}"
        if spec.require_network:
            observations = row.get("request_observations")
            if not isinstance(observations, list):
                return f"entry_scenario_observation_missing:{spec.name}"
            # If the declared exception occurred without any request, the
            # safety condition was not exercised.  A returned value or a
            # wrong exception is handled as a concrete outcome by the normal
            # scenario predicate below.
            raised = row.get("raised")
            returned = row.get("entry_returned")
            if not observations and (
                    (spec.expected_error is None and raised is None and returned is not None) or
                    (isinstance(raised, dict) and raised.get("type") == spec.expected_error)):
                return f"entry_scenario_not_reached:{spec.name}"
    return None


def _verdict(config: SafetyConfig, execution: dict) -> dict:
    if execution.get("status") != "OK":
        return {"verdict": "UNKNOWN", "reason": "sandbox_execution_incomplete", "execution": execution,
                "observation_summary": {"classification": "OUTER_SANDBOX_BLOCKED" if execution.get("status") == "BLOCKED" else "INCOMPLETE",
                                         "outer_sandbox_blocked": execution.get("status") == "BLOCKED", "incomplete": True}}
    observation_error = _execution_observation_error(execution)
    if observation_error:
        return {"verdict": "UNKNOWN", "reason": observation_error, "execution": execution,
                "observation_summary": {"classification": "INCOMPLETE", "outer_sandbox_blocked": False,
                                         "incomplete": True, "missing_or_invalid": observation_error}}
    # Scenario rows are trusted execution evidence.  A missing or malformed
    # row is an observation gap, not a failed business assertion; fail closed
    # as UNKNOWN so a skipped redirect/normal-return check cannot look like a
    # real FAIL or PASS.
    if not isinstance(execution.get("entry_scenarios"), list) or \
            len(execution.get("entry_scenarios", [])) != len(config.entry.scenarios):
        return {"verdict": "UNKNOWN", "reason": "entry_scenario_observation_incomplete",
                "execution": execution,
                "observation_summary": {"classification": "INCOMPLETE", "outer_sandbox_blocked": False,
                                         "incomplete": True, "missing_or_invalid": "entry_scenarios"}}
    scenario_rows = {x.get("name"): x for x in execution["entry_scenarios"] if isinstance(x, dict)}
    if any(spec.name not in scenario_rows for spec in config.entry.scenarios):
        return {"verdict": "UNKNOWN", "reason": "entry_scenario_observation_incomplete",
                "execution": execution,
                "observation_summary": {"classification": "INCOMPLETE", "outer_sandbox_blocked": False,
                                         "incomplete": True, "missing_or_invalid": "entry_scenarios"}}
    scenario_gap = _scenario_observation_gap(config, execution)
    if scenario_gap:
        return {"verdict": "UNKNOWN", "reason": scenario_gap,
                "execution": execution,
                "observation_summary": {"classification": "INCOMPLETE", "outer_sandbox_blocked": False,
                                         "incomplete": True, "missing_or_invalid": scenario_gap}}
    required = {
        "pytest": execution.get("pytest_exit_code") == 0,
        "required_pytest_tests": execution.get("pytest_observation", {}).get("required_tests_passed") is True,
        "entry_completed": ((execution.get("raised") is None and execution.get("entry_returned") is not None) or
                            (config.entry.expected_error and
                             (execution.get("raised") or {}).get("type") == config.entry.expected_error)),
        "required_entry_scenarios": _scenario_requirements(config, execution),
        "required_allowed_file_read": (not config.require_allowed_file_read) or any(
            x.get("classification") == "allowed" for x in execution.get("audit_events", [])),
        "no_forbidden_file_read": not bool(execution.get("forbidden_reads")),
        "no_out_of_scope_file_read": not bool(execution.get("out_of_scope_reads")),
        "no_credential_output": not bool(execution.get("credential_leaks")),
        "allowed_service_receipt": (not config.services) or any(x.get("service") == "allow" for x in execution.get("requests", [])),
        "allowed_service_path": (not config.services) or all(
            str(x.get("path", "")).startswith(config.services[0].path_prefix.rstrip("/") + "/") or
            str(x.get("path", "")) == config.services[0].path_prefix
            for x in execution.get("requests", []) if x.get("service") == "allow"),
        "required_service_credential": (not config.require_service_credential) or any(
            x.get("service") == "allow" and x.get("credential_ok") is True for x in execution.get("requests", [])),
        "no_forbidden_service_receipt": not any(x.get("service") == "forbidden" for x in execution.get("requests", [])),
        "no_unauthorized_connection": not bool(execution.get("unauthorized_connections")) and
                                       (bool(config.services) or not execution.get("requests")),
        "isolation_receipt": execution.get("isolation", {}).get("pytest_collection_in_sandbox") is True,
    }
    failed = [name for name, value in required.items() if not value]
    observed_violation = bool(execution.get("forbidden_reads") or execution.get("out_of_scope_reads") or execution.get("unauthorized_connections") or
                              any(x.get("service") == "forbidden" for x in execution.get("requests", [])) or
                              execution.get("credential_leaks"))
    return {"verdict": "PASS" if not failed else "FAIL", "required_checks": required,
            "failed_checks": failed, "execution": execution,
            "observation_summary": {"classification": "ACTUAL_VIOLATION" if observed_violation else "NO_OBSERVED_VIOLATION",
                                     "outer_sandbox_blocked": False, "incomplete": False},
            "scope": {"files": list(config.allowed_dirs), "services": [x.as_dict() for x in config.services],
                       "credential": "synthetic value; redacted in public report"},
            "limitations": execution.get("isolation", {}).get("uncovered", []) +
                           ["Only declared entry and pytest test paths are exercised"]}


def check_project(config_path: str | Path, *, output: str | Path | None = None,
                  project_root: str | Path | None = None) -> dict:
    """Run declared tests and entry in a disposable reviewed WSL lab."""
    config = load_config(config_path, project_root=project_root)
    module_relative = Path(config.entry.module.replace(".", "/") + ".py").as_posix()
    if not config.matches_source(module_relative):
        raise ValueError("entry module is outside project.source_scope")
    started = time.monotonic()
    temp_root = runtime_temp_root()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credproof-project-", dir=temp_root) as temporary:
        work = Path(temporary)
        project = work / "project"
        _copy_project(config.project_root, project)
        credential = "CP_LAB_" + uuid.uuid4().hex.upper()
        lab = _build_lab(config, work, credential)
        # Disable pytest stdout/stderr capture: otherwise output of a passing
        # test is hidden from the surrounding credential-channel check.
        test_args = ["-q", "-s", *config.tests]
        scenarios = tuple({"name": x.name, "request": x.request,
                           "expected_error": x.expected_error,
                           "require_network": x.require_network}
                          for x in config.entry.scenarios)
        execution = run_sandbox(project, lab, test_args, config.entry.module,
                                config.entry.callable, config.entry.request, credential,
                                config.timeout_seconds, allowed_dirs=config.allowed_dirs,
                                forbidden_dirs=config.forbidden_dirs,
                                service_path_prefix=config.services[0].path_prefix if config.services else "/",
                                require_service_credential=config.require_service_credential,
                                credential_env=config.credential_env,
                                entry_scenarios=scenarios,
                                optional_tests=config.optional_tests)
        report = _verdict(config, execution)
        report.update({"schema": "credproof.safety.report/v1", "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "project_tree_sha256": _digest_tree(project),
                       "duration_ms": round((time.monotonic() - started) * 1000, 2),
                       "config": config.to_public_dict()})
        # The synthetic credential and raw stdout are intentionally omitted from
        # the exported report. The execution record stays local for diagnosis.
        report["execution"] = _redact_execution(report["execution"], credential)
        if output:
            output = Path(output)
            if output.exists():
                raise ValueError("Refuse to overwrite an existing report")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report


def _redact_execution(value: dict, credential: str) -> dict:
    value = copy.deepcopy(value)
    def red(x):
        if isinstance(x, str): return x.replace(credential, "[SYNTHETIC_CREDENTIAL]")
        if isinstance(x, dict): return {red(k) if isinstance(k, str) else k: red(v) for k, v in x.items()}
        if isinstance(x, list): return [red(v) for v in x]
        return x
    return red(value)


def export_regression_tests(config_path: str | Path, destination: str | Path) -> Path:
    """Create a reusable pytest assertion which calls the same model-free check."""
    config = load_config(config_path)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("Refuse to overwrite an existing export directory")
    destination.mkdir(parents=True)
    test = '''"""CredProof reusable safety regression; generated from a reviewed project config."""
import os
from pathlib import Path
import tempfile
import pytest

@pytest.mark.credproof_safety
def test_credproof_safety_regression():
    if os.environ.get("CREDPROOF_INNER") == "1":
        pytest.skip("CredProof executes the project test suite in its outer sandbox")
    from credproof_safety import check_project
    configured_root = os.environ.get("CREDPROOF_PROJECT_ROOT")
    if configured_root:
        root = Path(configured_root)
    else:
        root = next((candidate for candidate in (Path(__file__).resolve().parent, *Path(__file__).resolve().parents)
                     if (candidate / "credproof.toml").is_file()), Path(__file__).resolve().parents[1])
    report_dir = root / ".credproof"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_fd, report_name = tempfile.mkstemp(prefix="consumer-report-", suffix=".json",
                                              dir=report_dir)
    os.close(report_fd)
    report_path = Path(report_name)
    report_path.unlink()
    report = check_project(root / "credproof.toml", output=report_path, project_root=root)
    assert report["verdict"] == "PASS", report
'''
    (destination / "test_credproof_safety.py").write_text(test, encoding="utf-8")
    (destination / "README.md").write_text(
        "# CredProof reusable regression\n\n"
        "Install the `credproof-safety` package and keep `credproof.toml` in the project root.\n"
        "Run `python -m credproof_safety check --config credproof.toml` before pytest.\n"
        "The generated test reruns the same model-free check; it does not trust a saved PASS, a web page, or a case ID.\n"
        "Declare the generated `tests/credproof-regression` path in `project.optional_tests`; its inner recursion guard is a wrapper check, not a business test.\n"
        "Register the `credproof_safety` pytest marker in the consumer project's pytest.ini or pyproject.toml.\n"
        "Each run writes a newly generated redacted safety report under `.credproof/consumer-report-*.json`; consumers may inspect it separately from pytest's exit code.\n"
        "The check uses an isolated WSL/bubblewrap lab and synthetic credential/service material.\n",
        encoding="utf-8")
    return destination
