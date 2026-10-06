"""Adapt one registered page task to the reviewed CredProof repair boundary.

The browser never supplies a project path or command.  ``agent_pilot.web``
passes a server-selected config and case ID; this adapter invokes the same
``request_repair`` entry used by the CLI and writes the historical UI record
shape only after the real boundary run has ended.  A blocked or incomplete
model run remains visible as such and never becomes a PASS badge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

from .agent import request_repair
from .config import load_config


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _authority(initial: dict) -> dict:
    summary = initial.get("observation_summary") if isinstance(initial, dict) else {}
    classification = summary.get("classification") if isinstance(summary, dict) else None
    if classification == "ACTUAL_VIOLATION":
        confirmed = "CONFIRMED_LEAK"
    elif classification == "NO_OBSERVED_VIOLATION":
        confirmed = "NO_LEAK_OBSERVED"
    else:
        confirmed = "UNKNOWN"
    return {"confirmed": confirmed, "repair_authorized": confirmed == "CONFIRMED_LEAK",
            "source": "credproof_safety.check_project", "classification": classification}


def _observation(initial: dict) -> list[dict]:
    if not isinstance(initial, dict):
        return []
    execution = initial.get("execution") or {}
    return [{
        "id": "initial-project-check",
        "tool": "check_project",
        "hypothesis": "程序确认当前对象是否存在已声明的泄露或边界违规；模型文字不替代此证据。",
        "observation": {
            "verdict": initial.get("verdict", "UNKNOWN"),
            "required_checks": initial.get("required_checks", {}),
            "failed_checks": initial.get("failed_checks", []),
            "access_summary": execution.get("access_summary", {}),
            "pytest_observation": execution.get("pytest_observation", {}),
        },
        "observed_at": initial.get("checked_at_utc"),
    }]


def _adapt(config_path: Path, output: Path, project_id: str, case_id: str, repair: dict) -> dict:
    config = load_config(config_path)
    entry = config.project_root / (config.entry.module.replace(".", "/") + ".py")
    original = entry.read_text(encoding="utf-8") if entry.is_file() else ""
    artifact = Path(repair.get("artifact_dir", "")) if repair.get("artifact_dir") else None
    candidate = artifact / "candidate" / (config.entry.module.replace(".", "/") + ".py") if artifact else None
    candidate_text = candidate.read_text(encoding="utf-8") if candidate and candidate.is_file() else original
    method = output / "comparison" / case_id / "C-agent"
    method.mkdir(parents=True, exist_ok=True)
    (method / "original.py").write_text(original, encoding="utf-8", newline="\n")
    (method / "final-candidate.py").write_text(candidate_text, encoding="utf-8", newline="\n")
    initial = repair.get("initial") if isinstance(repair.get("initial"), dict) else {}
    final = repair.get("final") if isinstance(repair.get("final"), dict) else {}
    if not final:
        final = {"verdict": "UNKNOWN", "reasons": [repair.get("reason", "no_final_report")],
                 "observation_summary": {"classification": "INCOMPLETE", "incomplete": True}}
    model = repair.get("model") if isinstance(repair.get("model"), dict) else {}
    task_status = repair.get("task_status") or ("INCOMPLETE" if repair.get("status") != "OK" else "UNKNOWN")
    row = {
        "schema": "credproof.web-live-record/v1",
        "method": "C-agent",
        "execution_kind": "real-local-model-inference",
        "project_id": project_id,
        "case_id": case_id,
        "project_config": config_path.name,
        "initial_authority": _authority(initial),
        "diagnosis": {"diagnosis": "模型意见与程序初始证据分开保存；详见模型轨迹。",
                      "initially_leaking": _authority(initial)["confirmed"] == "CONFIRMED_LEAK"},
        "final_validation": final,
        "task": {"task_status": task_status, "reason": repair.get("reason")},
        "model": model,
        "tool_trace": repair.get("tool_trace", []),
        "observations": _observation(initial),
        "candidate_count": (repair.get("budgets") or {}).get("max_candidates") if isinstance(repair.get("budgets"), dict) else None,
        "source_changed": original != candidate_text,
        "source_sha256": _sha(method / "original.py"),
        "candidate_sha256": _sha(method / "final-candidate.py"),
        "artifact_dir": repair.get("artifact_dir"),
        "model_boundary": repair.get("model_boundary"),
        "paid_api_used": repair.get("paid_api_used", False),
        "web_adapter": {"status": "ADAPTED", "source": "credproof_safety.agent.request_repair",
                         "registered_case_only": True, "project_identity": project_id},
    }
    _write(method / "result.json", row)
    if initial:
        _write(method / "initial-evidence.json", _observation(initial))
    return row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    report_path = args.output / "repair.json"
    try:
        result = request_repair(args.config.resolve(strict=True), output=report_path)
    except Exception as exc:  # preserve a visible incomplete task for the page
        result = {"schema": "credproof.safety.agent/v2", "status": "BLOCKED",
                  "reason": "web_adapter_error", "detail": type(exc).__name__,
                  "paid_api_used": False}
        _write(report_path, result)
    _adapt(args.config.resolve(), args.output, args.project_id, args.case_id, result)
    print(json.dumps({"status": result.get("status"), "task_status": result.get("task_status"),
                      "project_id": args.project_id, "case_id": args.case_id}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
