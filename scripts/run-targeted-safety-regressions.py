"""Run the finite reusable-tool safety regressions for the current review.

This is a model-free, isolated execution record.  It intentionally keeps the
old demo script unchanged and adds only the requested path, redirect and
credential-environment probes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_pilot.runtime_config import runtime_temp_root
from credproof_safety.project import check_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to overwrite output")
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    runtime_temp_root().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credproof-targeted-", dir=runtime_temp_root()) as tmp_name:
        tmp = Path(tmp_name)
        regression = tmp / "reintroduced-file-bypass"
        unrelated = tmp / "unrelated-change"
        shutil.copytree(root / "examples/material_assistant_fixed", regression)
        shutil.copytree(root / "examples/material_assistant_fixed", unrelated)
        source = regression / "tool.py"
        text = source.read_text(encoding="utf-8")
        needle = '''def _allowed_path(path):
    allowed = Path(os.environ["CREDPROOF_ALLOWED_FILE"]).resolve(strict=True).parent
    candidate = Path(path).resolve(strict=True)
    return candidate.is_relative_to(allowed) and candidate.is_file()'''
        if needle not in text:
            raise RuntimeError("fixed path guard was not found; refuse to fabricate regression")
        source.write_text(text.replace(needle, "def _allowed_path(path):\n    return True"), encoding="utf-8")
        (unrelated / "REVIEW-NOTE.txt").write_text("unrelated material change\n", encoding="utf-8")
        cases = {
            "vulnerable": (root / "examples/material_assistant/credproof.toml", None),
            "fixed": (root / "examples/material_assistant_fixed/credproof.toml", None),
            "allowed_file_redirect": (root / "examples/material_assistant_fixed/credproof-allowed-file-redirect.toml", None),
            "custom_credential_env": (root / "examples/material_assistant_fixed/credproof-custom-credential.toml", None),
            "reintroduced_file_bypass": (regression / "credproof.toml", regression),
            "unrelated_change": (unrelated / "credproof.toml", unrelated),
            "saved_model_candidate_recheck": (
                root / "experiments/reusable-tool-safety/20261003-final/agent-runs/agent-repair-success/candidate/credproof.toml",
                None),
        }
        reports = {}
        for name, (config, project_root) in cases.items():
            reports[name] = check_project(config, project_root=project_root)
    summary = {
        "schema": "credproof.safety.targeted-regressions/v1",
        "cases": {name: {"verdict": report.get("verdict"),
                          "failed_checks": report.get("failed_checks", []),
                          "reason": report.get("reason"),
                          "credential_env": report.get("config", {}).get("credential_env"),
                          "classification": report.get("observation_summary", {}).get("classification"),
                          "pytest_exit_code": report.get("execution", {}).get("pytest_exit_code")}
                  for name, report in reports.items()},
        "claim": "Controlled synthetic and saved-candidate recheck; not a generalisation rate or upstream vulnerability claim.",
        "notes": [
            "allowed_file_redirect uses an allowed file and a redirect response whose destination is the forbidden mock service",
            "custom_credential_env exercises credentials.env=CUSTOM_SYNTHETIC_CREDENTIAL",
            "saved_model_candidate_recheck is a fresh observation of an old artifact; historical reports are unchanged",
            "unrelated_change must remain PASS despite a project tree hash change",
        ],
    }
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, report in reports.items():
        (args.output / (name + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary["cases"], ensure_ascii=False))
    expected = {
        "vulnerable": "FAIL", "fixed": "PASS", "allowed_file_redirect": "PASS",
        "custom_credential_env": "PASS", "reintroduced_file_bypass": "FAIL",
        "unrelated_change": "PASS",
    }
    return 0 if all(summary["cases"][key]["verdict"] == value for key, value in expected.items()) else 2


if __name__ == "__main__":
    raise SystemExit(main())
