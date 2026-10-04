"""Run real pytest-plugin observation regressions and write raw reports."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import platform

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety import check_project


CONFIG = '''schema = "credproof.project-safety/v1"

[project]
root = "."
tests = ["{tests}"]
optional_tests = [{optional_tests}]
source_scope = ["*.py", "**/*.py"]
mutable_scope = ["*.py", "**/*.py"]

[files]
allowed_dirs = ["data"]
forbidden_dirs = ["secrets"]
require_allowed_file_read = false

[network]
require_service_credential = false
allowed_services = []

[credentials]
env = "CREDPROOF_TEST_CREDENTIAL"

[entry]
module = "tool"
callable = "run"
request = {{ resource = "observer-regression" }}

[limits]
timeout_seconds = 30
report_dir = ".credproof"
'''

CASES = {
    "normal_pass": {
        "tests": "tests",
        "optional": [],
        "files": {"tests/test_required.py": "def test_smoke():\n    assert True\n"},
    },
    "partial_required_skip": {
        "tests": "tests",
        "optional": [],
        "files": {"tests/test_required.py": (
            "import pytest\n\n"
            "def test_smoke():\n    assert True\n\n"
            "@pytest.mark.skip(reason='required case unavailable')\n"
            "def test_business():\n    assert True\n")},
    },
    "all_required_skip": {
        "tests": "tests",
        "optional": [],
        "files": {"tests/test_required.py": (
            "import pytest\n\n"
            "@pytest.mark.skip(reason='required case unavailable')\n"
            "def test_business():\n    assert True\n")},
    },
    "required_xfail": {
        "tests": "tests",
        "optional": [],
        "files": {"tests/test_required.py": (
            "import pytest\n\n"
            "@pytest.mark.xfail(strict=True, reason='known failing requirement')\n"
            "def test_business():\n    assert False\n")},
    },
    "missing_required": {
        "tests": "tests/missing_test.py",
        "optional": [],
        "files": {"tests/test_present.py": "def test_present():\n    assert True\n"},
    },
    "required_assertion_failure": {
        "tests": "tests",
        "optional": [],
        "files": {"tests/test_required.py": "def test_business():\n    assert False\n"},
    },
    "optional_skip": {
        "tests": "tests",
        "optional": ["tests/test_optional.py"],
        "files": {
            "tests/test_required.py": "def test_business():\n    assert True\n",
            "tests/test_optional.py": (
                "import pytest\n\n"
                "@pytest.mark.skip(reason='declared optional')\n"
                "def test_optional():\n    assert True\n"),
        },
    },
}


def _write_fixture(case_root: Path, definition: dict) -> Path:
    project = case_root / "project"
    project.mkdir(parents=True)
    (project / "tool.py").write_text(
        "def run(request):\n    return {'ok': True, 'resource': request.get('resource')}\n",
        encoding="utf-8")
    for relative, content in definition["files"].items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    optional = ", ".join(json.dumps(value) for value in definition["optional"])
    (project / "credproof.toml").write_text(
        CONFIG.format(tests=definition["tests"], optional_tests=optional), encoding="utf-8")
    return project


def _summary(report: dict) -> dict:
    execution = report.get("execution", {})
    observation = execution.get("pytest_observation", {})
    return {
        "verdict": report.get("verdict"),
        "reason": report.get("reason"),
        "pytest_exit_code": execution.get("pytest_exit_code"),
        "pytest_observation": observation,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to overwrite output")
    args.output.mkdir(parents=True)
    results = {}
    for name, definition in CASES.items():
        case_root = args.output / name
        project = _write_fixture(case_root, definition)
        report_path = case_root / "report.json"
        report = check_project(project / "credproof.toml", output=report_path, project_root=project)
        results[name] = _summary(report)
    metadata = {
        "schema": "credproof.pytest-observer-regression/v1",
        "python": sys.version,
        "python_implementation": platform.python_implementation(),
        "pytest": __import__("pytest").__version__,
        "command": [sys.executable, "scripts/run-pytest-observer-regressions.py",
                     "--output", str(args.output)],
        "model_called": False,
        "results_derived_from": "each case/report.json execution.pytest_observation",
        "cases": results,
        "claim": "Protocol regression using real pytest plugin callbacks and the actual verdict function; synthetic fixtures only.",
    }
    (args.output / "summary.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": metadata["schema"], "python": metadata["python"],
                      "pytest": metadata["pytest"], "cases": results}, ensure_ascii=False))
    expected = {
        "normal_pass": "PASS",
        "partial_required_skip": "UNKNOWN",
        "all_required_skip": "UNKNOWN",
        "required_xfail": "FAIL",
        "missing_required": "UNKNOWN",
        "required_assertion_failure": "FAIL",
        "optional_skip": "PASS",
    }
    return 0 if all(results[key]["verdict"] == value for key, value in expected.items()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
