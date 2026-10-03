"""Run the bounded reusable-entry demonstration on disposable copies.

The three reports are deliberately kept together: vulnerable FAIL, repaired
PASS, and a fresh regression FAIL after reintroducing one flaw. The script does
not mutate either tracked example or invoke the local model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from credproof_safety.project import check_project
from agent_pilot.runtime_config import runtime_temp_root


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to overwrite output")
    args.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1]
    runtime_temp_root().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="credproof-demo-", dir=runtime_temp_root()) as tmp:
        tmp = Path(tmp)
        vulnerable = tmp / "vulnerable"; fixed = tmp / "fixed"; regression = tmp / "regression"
        shutil.copytree(root / "examples/material_assistant", vulnerable)
        shutil.copytree(root / "examples/material_assistant_fixed", fixed)
        shutil.copytree(fixed, regression)
        source = regression / "tool.py"
        text = source.read_text(encoding="utf-8")
        text = text.replace("return candidate.is_relative_to(allowed) and candidate.is_file()", "return True")
        source.write_text(text, encoding="utf-8")
        reports = {
            "vulnerable": check_project(vulnerable / "credproof.toml", project_root=vulnerable),
            "fixed": check_project(fixed / "credproof.toml", project_root=fixed),
            "reintroduced_file_bypass": check_project(regression / "credproof.toml", project_root=regression),
        }
    (args.output / "summary.json").write_text(json.dumps({
        "schema": "credproof.safety.reusable-demo/v1",
        "cases": {name: {"verdict": row.get("verdict"), "failed_checks": row.get("failed_checks", []),
                          "pytest_exit_code": row.get("execution", {}).get("pytest_exit_code")}
                  for name, row in reports.items()},
        "reports": reports,
        "claim": "Controlled synthetic example; not a generalisation rate or upstream vulnerability claim.",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for name, report in reports.items():
        (args.output / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({name: row.get("verdict") for name, row in reports.items()}, ensure_ascii=False))
    return 0 if reports["vulnerable"]["verdict"] == "FAIL" and reports["fixed"]["verdict"] == "PASS" and reports["reintroduced_file_bypass"]["verdict"] == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
