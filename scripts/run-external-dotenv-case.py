"""Run the fixed external python-dotenv v1.2.2 integration case."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.project import check_project


def main():
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    if a.output.exists(): raise SystemExit("refuse to overwrite output")
    a.output.mkdir(parents=True)
    root = Path(__file__).resolve().parents[1] / "examples/external/python-dotenv-v1.2.2"
    before = check_project(root / "credproof.toml", project_root=root)
    after = check_project(root / "credproof-fixed.toml", project_root=root)
    result = {"schema":"credproof.external-case/v1", "provenance": json.loads((root/"provenance.json").read_text()),
              "artificial_injection": True,
              "before": {"verdict":before.get("verdict"),"failed_checks":before.get("failed_checks",[]),"pytest":before.get("execution",{}).get("pytest_exit_code")},
              "after": {"verdict":after.get("verdict"),"failed_checks":after.get("failed_checks",[]),"pytest":after.get("execution",{}).get("pytest_exit_code")},
              "full_before":before,"full_after":after}
    (a.output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["before"],ensure_ascii=False), json.dumps(result["after"],ensure_ascii=False))
    return 0 if before.get("verdict")=="FAIL" and after.get("verdict")=="PASS" else 2


if __name__ == "__main__": raise SystemExit(main())
