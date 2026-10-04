"""Run the external python-dotenv integration case in an independent copy.

The tracked fixture is only the reproducible source snapshot.  Every check is
performed against a disposable copy outside the CredProof repository so that
the result exercises the same project-entry path a user would use for an
external checkout.  The copy is never edited in place; the regression variant
is modified only after the fixed result has been recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.project import check_project


def _tree_digest(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.is_symlink():
            rows.append((path.relative_to(root).as_posix(), hashlib.sha256(path.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()


def _stage(source: Path, destination: Path) -> None:
    """Copy an external project without carrying its VCS or Python cache."""
    shutil.copytree(
        source,
        destination,
        symlinks=True,
        ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", ".credproof"),
    )


def _run_case(root: Path) -> dict:
    before = check_project(root / "credproof.toml", project_root=root)
    after = check_project(root / "credproof-fixed.toml", project_root=root)

    regression = root.parent / (root.name + "-reintroduced")
    _stage(root, regression)
    fixed_entry = regression / "credproof_entry_fixed.py"
    text = fixed_entry.read_text(encoding="utf-8")
    guard = "if not candidate.is_relative_to(allowed):"
    if guard not in text:
        raise RuntimeError("fixed external adapter guard was not found")
    fixed_entry.write_text(text.replace(guard, "if False:"), encoding="utf-8")
    regression_result = check_project(regression / "credproof-fixed.toml", project_root=regression)

    unrelated = root.parent / (root.name + "-unrelated")
    _stage(root, unrelated)
    (unrelated / "review-note.txt").write_text("unrelated change\n", encoding="utf-8")
    unrelated_result = check_project(unrelated / "credproof-fixed.toml", project_root=unrelated)
    return {
        "before": before,
        "after": after,
        "reintroduced_defect": regression_result,
        "unrelated_change": unrelated_result,
        "staging": {
            "source_is_tracked_fixture": True,
            "checked_copy_outside_repository": not root.resolve().is_relative_to(Path(__file__).resolve().parents[1]),
            "source_tree_sha256": _tree_digest(root),
            "checked_tree_sha256": _tree_digest(root),
            "regression_is_disposable_copy": True,
            "unrelated_change_is_disposable_copy": True,
        },
    }


def main():
    p = argparse.ArgumentParser(); p.add_argument("--output", type=Path, required=True); a = p.parse_args()
    if a.output.exists(): raise SystemExit("refuse to overwrite output")
    a.output.mkdir(parents=True)
    source = Path(__file__).resolve().parents[1] / "examples/external/python-dotenv-v1.2.2"
    repo_root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix="credproof-external-project-") as staging:
        external_root = Path(staging) / source.name
        _stage(source, external_root)
        case = _run_case(external_root)
    result = {"schema":"credproof.external-case/v2", "provenance": json.loads((source/"provenance.json").read_text()),
              "artificial_injection": True,
              "project_source": "tracked external fixture staged to a disposable directory outside the CredProof repository",
              "repository_root_for_relation": repo_root.name,
              "cases": {name: {"verdict": row.get("verdict"), "failed_checks": row.get("failed_checks",[]),
                               "pytest": row.get("execution",{}).get("pytest_exit_code")}
                        for name, row in case.items() if name in {"before", "after", "reintroduced_defect", "unrelated_change"}},
              "full_before":case["before"],"full_after":case["after"],
              "full_reintroduced_defect":case["reintroduced_defect"],
              "full_unrelated_change":case["unrelated_change"],
              "staging":case["staging"]}
    (a.output/"summary.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(result["cases"],ensure_ascii=False))
    cases = result["cases"]
    return 0 if (cases["before"]["verdict"] == "FAIL" and
                  cases["after"]["verdict"] == "PASS" and
                  cases["reintroduced_defect"]["verdict"] == "FAIL" and
                  cases["unrelated_change"]["verdict"] == "PASS") else 2


if __name__ == "__main__": raise SystemExit(main())
