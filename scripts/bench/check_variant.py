"""Run one patch variant of a benchmark target through the real CredProof checker.

The target project is copied to a disposable directory, its configured entry
file is replaced by --source, and credproof_safety.check_project runs in the
usual isolation (WSL on Windows, native bubblewrap on Linux). Writes the full
redacted report and a compact record (bench-check/v1). Never executes the
patch outside the checker.

    python scripts/bench/check_variant.py --target examples/bench/b01-ticket-digest \
        --source examples/bench/b01-ticket-digest/reference_fix.py --output out/b01-fix.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from credproof_safety.config import load_config  # noqa: E402
from credproof_safety.project import check_project  # noqa: E402


def compact(report: dict, source: bytes, target: str, label: str) -> dict:
    execution = report.get("execution") or {}
    observation = execution.get("pytest_observation") or {}
    requests = execution.get("requests") or []
    return {
        "schema": "credproof.bench-check/v1",
        "target": target,
        "label": label,
        "source_sha256": hashlib.sha256(source.replace(b"\r\n", b"\n")).hexdigest(),
        "verdict": report.get("verdict"),
        "reason": report.get("reason"),
        "failed_checks": report.get("failed_checks"),
        "leak_channels": execution.get("credential_leaks"),
        "forbidden_reads": len(execution.get("forbidden_reads") or []),
        "out_of_scope_reads": len(execution.get("out_of_scope_reads") or []),
        "forbidden_service_receipts": sum(r.get("service") == "forbidden" for r in requests),
        "credential_sent_to_forbidden": sum(r.get("service") == "forbidden" and bool(r.get("credential_ok")) for r in requests),
        "pytest": {"exit_code": execution.get("pytest_exit_code"), "collected": observation.get("collected"),
                   "executed": observation.get("executed"), "passed": observation.get("passed"),
                   "failed": observation.get("failed"), "skipped": observation.get("skipped")},
        "business_tests_all_passed": execution.get("pytest_exit_code") == 0 and observation.get("required_tests_passed") is True,
        "checked_at_utc": report.get("checked_at_utc"),
        "duration_ms": report.get("duration_ms"),
        "project_tree_sha256": report.get("project_tree_sha256"),
    }


def check(target: Path, source: Path, label: str = "") -> tuple[dict, dict]:
    target = target.resolve(strict=True)
    project = target / "project" if (target / "project").is_dir() else target
    config = load_config(project / "credproof.toml")
    entry = config.entry.module.replace(".", "/") + ".py"
    data = source.read_bytes()
    with tempfile.TemporaryDirectory(prefix="credproof-bench-") as tmp:
        copy = Path(tmp) / "project"
        shutil.copytree(project, copy, ignore=shutil.ignore_patterns("__pycache__", ".credproof", "*.pyc"))
        (copy / entry).write_bytes(data)
        report = check_project(copy / "credproof.toml", project_root=copy)
    return report, compact(report, data, target.name, label or source.name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--label", default="")
    parser.add_argument("--output", type=Path, required=True, help="compact record; full report goes next to it")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("refuse to overwrite an existing record")
    started = time.time()
    report, record = check(args.target, args.source, args.label)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    args.output.write_text(json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: record[k] for k in ("target", "label", "verdict", "failed_checks", "leak_channels", "business_tests_all_passed")},
                     ensure_ascii=False), f"{time.time() - started:.1f}s")


if __name__ == "__main__":
    main()
