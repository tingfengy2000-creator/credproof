"""Unified re-check of every historical AI patch under the current rule set (issue #2).

Each patch from docs/report-v2/data/ai-patch-dataset.json is swapped into one
fixed project and checked once with the real checker:
  * material_assistant patches -> dev35 human-review baseline project
    (4 business tests + normal-return and redirect scenarios);
  * python-dotenv patches -> examples/external/python-dotenv-v1.2.2.
Known-good and known-bad controls run in the same batch. No model is called.

    python scripts/bench/recheck_history.py --output <new directory>
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_variant import check  # noqa: E402

PROJECTS = {
    "material_assistant": ROOT / "docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/runs/human-review/939e25f42bb142f39567c5cb644ebc6d/baseline/project",
    "python-dotenv": ROOT / "examples/external/python-dotenv-v1.2.2",
}
CONTROLS = [
    ("control:vulnerable_original", "material_assistant", "examples/material_assistant/tool.py", "FAIL"),
    ("control:reference_fix", "material_assistant", "examples/material_assistant_fixed/tool.py", "PASS"),
    ("control:developer_revision", "material_assistant", "docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/public-bundle/candidate.py", "PASS"),
    ("control:dotenv_injected_defect", "python-dotenv", "examples/external/python-dotenv-v1.2.2/credproof_entry.py", "FAIL"),
    ("control:dotenv_fixed", "python-dotenv", "examples/external/python-dotenv-v1.2.2/credproof_entry_fixed.py", "PASS"),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("new output directory required")
    args.output.mkdir(parents=True)
    dataset = json.loads((ROOT / "docs/report-v2/data/ai-patch-dataset.json").read_text(encoding="utf-8"))
    jobs = [(f"patch:{p['id']:02d}", p["project"], p["source"], None) for p in dataset["patches"]] + CONTROLS
    rows = []
    for label, project, source, expected in jobs:
        started = time.time()
        report, record = check(PROJECTS[project], ROOT / source, label)
        name = label.replace(":", "-")
        (args.output / f"{name}.report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        record.update(project=project, source=source, expected=expected)
        rows.append(record)
        print(f"{label:34} {record['verdict']:7} green={record['business_tests_all_passed']!s:5} "
              f"{','.join(record['failed_checks'] or []) or '-'}  leaks={record['leak_channels']}  {time.time() - started:.1f}s")
    patches = [r for r in rows if r["label"].startswith("patch:")]
    controls = [r for r in rows if r["label"].startswith("control:")]
    summary = {
        "schema": "credproof.history-recheck/v1",
        "host": platform.platform(), "python": platform.python_version(),
        "patches": len(patches),
        "accepted": sum(r["verdict"] == "PASS" for r in patches),
        "fail": sum(r["verdict"] == "FAIL" for r in patches),
        "unknown": sum(r["verdict"] == "UNKNOWN" for r in patches),
        "business_tests_all_passed": sum(r["business_tests_all_passed"] for r in patches),
        "business_green_but_rejected": sum(r["business_tests_all_passed"] and r["verdict"] != "PASS" for r in patches),
        "credential_leak": sum(bool(r["leak_channels"]) for r in patches),
        "controls_as_expected": all(r["verdict"] == r["expected"] for r in controls),
        "controls": {r["label"]: r["verdict"] for r in controls},
    }
    (args.output / "records.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
