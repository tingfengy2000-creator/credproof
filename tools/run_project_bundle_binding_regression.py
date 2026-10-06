"""Run the finite project-bundle identity regression without a model.

The script copies only the reviewed candidate and live-record metadata into a
temporary directory.  It deliberately records rejection reasons instead of
repairing a changed object or rewriting its old validation digest.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.project_bundle import export_project_bundle, recheck_project_bundle


def prepare(method: Path, work: Path, label: str, mutate) -> Path:
    destination = work / label
    artifact = destination / "artifact"
    candidate = artifact / "candidate"
    candidate.parent.mkdir(parents=True)
    source_result = json.loads((method / "result.json").read_text(encoding="utf-8"))
    source_candidate = Path(source_result["artifact_dir"]) / "candidate"
    shutil.copytree(source_candidate, candidate)
    live = destination / "method"
    live.mkdir()
    for name in ("original.py", "final-candidate.py"):
        shutil.copyfile(method / name, live / name)
    source_result["artifact_dir"] = str(artifact)
    (live / "result.json").write_text(json.dumps(source_result), encoding="utf-8")
    mutate(candidate)
    return live


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    method = args.method.resolve(strict=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="credproof-bundle-binding-"))
    result = {
        "schema": "credproof.project-bundle-binding-regression/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_invoked": False,
        "method": method.as_posix().split("/runs/")[-1] if "/runs/" in method.as_posix() else "reviewed-live-record",
        "cases": [],
    }
    try:
        # The unmodified reviewed record is exported normally.
        normal = work / "normal"
        normal_result = export_project_bundle(method, normal)
        result["cases"].append({"id": "normal_export", "status": normal_result["status"],
                                "project_tree_sha256": normal_result["project_tree_sha256"]})

        mutations = {
            "candidate_changed_before_export": lambda root: (root / "tool.py").write_text(
                (root / "tool.py").read_text(encoding="utf-8") + "\n# changed before export\n", encoding="utf-8"),
            "configuration_changed_before_export": lambda root: (root / "credproof.toml").write_text(
                (root / "credproof.toml").read_text(encoding="utf-8") + "\n# changed before export\n", encoding="utf-8"),
            "required_tests_changed_before_export": lambda root: (root / "tests/test_business.py").write_text(
                (root / "tests/test_business.py").read_text(encoding="utf-8") + "\n# changed before export\n", encoding="utf-8"),
        }
        for case_id, mutate in mutations.items():
            changed_method = prepare(method, work, case_id, mutate)
            try:
                export_project_bundle(changed_method, work / (case_id + "-bundle"))
            except Exception as exc:  # expected fail-closed path
                result["cases"].append({"id": case_id, "status": "REJECTED",
                                        "error": type(exc).__name__ + ":" + str(exc)})
            else:
                result["cases"].append({"id": case_id, "status": "UNEXPECTED_EXPORT"})

        # A post-export change cannot reuse the old report; recheck must return
        # UNKNOWN before any fresh execution is trusted.
        (normal / "project/tool.py").write_text(
            (normal / "project/tool.py").read_text(encoding="utf-8") + "\n# changed after export\n",
            encoding="utf-8")
        rechecked = recheck_project_bundle(normal, work / "post-change.json")
        result["cases"].append({"id": "changed_after_export", "status": rechecked["validation"]["verdict"],
                                "reasons": rechecked["prior_report_reasons"],
                                "prior_report_applicable": rechecked["prior_report_applicable"]})
    finally:
        shutil.rmtree(work, ignore_errors=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
