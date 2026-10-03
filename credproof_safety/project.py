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


def _digest_tree(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rows.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()


def _copy_project(root: Path, destination: Path) -> None:
    ignored = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".credproof", "*.pyc")
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
    (allowed / "brief.txt").write_text("authorized material for the sample tool\n", encoding="utf-8")
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


def _verdict(config: SafetyConfig, execution: dict) -> dict:
    if execution.get("status") != "OK":
        return {"verdict": "UNKNOWN", "reason": "sandbox_execution_incomplete", "execution": execution,
                "observation_summary": {"classification": "OUTER_SANDBOX_BLOCKED" if execution.get("status") == "BLOCKED" else "INCOMPLETE",
                                         "outer_sandbox_blocked": execution.get("status") == "BLOCKED", "incomplete": True}}
    required = {
        "pytest": execution.get("pytest_exit_code") == 0,
        "entry_completed": ((execution.get("raised") is None and execution.get("entry_returned") is not None) or
                            (config.entry.expected_error and
                             (execution.get("raised") or {}).get("type") == config.entry.expected_error)),
        "required_allowed_file_read": (not config.require_allowed_file_read) or any(
            x.get("classification") == "allowed" for x in execution.get("audit_events", [])),
        "no_forbidden_file_read": not bool(execution.get("forbidden_reads")),
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
    observed_violation = bool(execution.get("forbidden_reads") or execution.get("unauthorized_connections") or
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
    temp_root = Path(os.environ.get("CREDPROOF_RUNTIME_TEMP", "E:/CredProof-local-runtime/credproof-runs"))
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credproof-project-", dir=temp_root) as temporary:
        work = Path(temporary)
        project = work / "project"
        _copy_project(config.project_root, project)
        credential = "CP_LAB_" + uuid.uuid4().hex.upper()
        lab = _build_lab(config, work, credential)
        test_args = ["-q", *config.tests]
        execution = run_sandbox(project, lab, test_args, config.entry.module,
                                config.entry.callable, config.entry.request, credential,
                                config.timeout_seconds, allowed_dirs=config.allowed_dirs,
                                forbidden_dirs=config.forbidden_dirs,
                                service_path_prefix=config.services[0].path_prefix if config.services else "/",
                                require_service_credential=config.require_service_credential)
        report = _verdict(config, execution)
        report.update({"schema": "credproof.safety.report/v1", "checked_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "project_tree_sha256": _digest_tree(config.project_root),
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
import pytest

@pytest.mark.credproof_safety
def test_credproof_safety_regression():
    if os.environ.get("CREDPROOF_INNER") == "1":
        pytest.skip("CredProof executes the project test suite in its outer sandbox")
    from credproof_safety import check_project
    root = Path(os.environ.get("CREDPROOF_PROJECT_ROOT", Path(__file__).resolve().parents[1]))
    report = check_project(root / "credproof.toml", project_root=root)
    assert report["verdict"] == "PASS", report
'''
    (destination / "test_credproof_safety.py").write_text(test, encoding="utf-8")
    (destination / "README.md").write_text(
        "# CredProof reusable regression\n\n"
        "Install the `credproof-safety` package and keep `credproof.toml` in the project root.\n"
        "Run `python -m credproof_safety check --config credproof.toml` before pytest.\n"
        "The generated test reruns the same model-free check; it does not trust a saved PASS, a web page, or a case ID.\n"
        "The check uses an isolated WSL/bubblewrap lab and synthetic credential/service material.\n",
        encoding="utf-8")
    return destination
