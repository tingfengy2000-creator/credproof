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
import importlib.metadata

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
    execution = initial.get('execution') or {}
    channels = execution.get('credential_leaks')
    if classification == "ACTUAL_VIOLATION":
        confirmed = "CONFIRMED_LEAK" if isinstance(channels, list) and channels else "CONFIRMED_VIOLATION"
    elif classification == "NO_OBSERVED_VIOLATION":
        confirmed = "NO_LEAK_OBSERVED"
    else:
        confirmed = "UNKNOWN"
    return {"confirmed": confirmed, "repair_authorized": classification == "ACTUAL_VIOLATION",
            "source": "credproof_safety.check_project", "classification": classification,
            "credential_channels": channels,
            "file_violation": bool(execution.get('forbidden_reads') or execution.get('out_of_scope_reads')),
            "network_violation": bool(execution.get('unauthorized_connections') or
                any(x.get('service') == 'forbidden' for x in execution.get('requests', [])))}


def execution_summary(repair: dict) -> dict:
    """Count host-accepted operations, independently of budget and model claims."""
    root = Path(repair['artifact_dir']) if repair.get('artifact_dir') else None
    model = repair.get('model') or {}
    budgets = repair.get('budgets') if isinstance(repair.get('budgets'), dict) else {}
    if not budgets and root and (root / 'model-work/model-result.json').is_file():
        try:
            staged = json.loads((root / 'model-work/model-result.json').read_text(encoding='utf-8'))
            budgets = staged.get('budgets') if isinstance(staged.get('budgets'), dict) else {}
        except (OSError, ValueError, TypeError):
            budgets = {}
    accepted, verified, refused, requests, inconsistencies = [], [], [], [], []
    if root and root.is_dir():
        rpc = root / 'rpc'
        for path in sorted(rpc.glob('request-*.json')):
            request = json.loads(path.read_text(encoding='utf-8'))
            response_path = path.with_name(path.name.replace('request-', 'response-', 1))
            response = json.loads(response_path.read_text(encoding='utf-8')) if response_path.is_file() else {}
            requests.append({'id': request.get('id'), 'tool': request.get('tool'), 'status': response.get('status')})
            if response.get('status') == 'REJECTED':
                refused.append({'tool': request.get('tool'), 'reason': response.get('reason')})
            if request.get('tool') == 'submit_patch' and response.get('status') == 'ACCEPTED_FOR_VERIFICATION':
                number = response.get('candidate')
                historical = root / 'verification-history' / ('candidate-%02d.py' % number)
                code = (request.get('arguments') or {}).get('code')
                if not historical.is_file() or not isinstance(code, str) or historical.read_text(encoding='utf-8') != code:
                    inconsistencies.append('accepted_candidate_history_mismatch:' + str(number))
                accepted.append({'candidate': number, 'sha256': _sha(historical) if historical.is_file() else None})
        for path in sorted((root / 'verification-history').glob('verification-*.json')):
            verified.append({'file': path.name, 'verdict': json.loads(path.read_text(encoding='utf-8')).get('verdict')})
    trace = root / 'model-work/model-trace' if root else None
    model_requests = sorted(trace.glob('model-*-request.json')) if trace and trace.is_dir() else []
    model_responses = sorted(trace.glob('model-*-response.json')) if trace and trace.is_dir() else []
    error = model.get('error')
    termination = ('MODEL_REQUEST_WALL_CLOCK_TIMEOUT' if isinstance(error, str) and 'wall-clock timeout' in error
                   else repair.get('reason') or model.get('status') or 'NO_MODEL_EXECUTION')
    return {'candidate_cap': budgets.get('max_candidates'),
            'model_call_cap': budgets.get('max_model_calls'),
            'accepted_candidates': len(accepted), 'candidate_history': accepted,
            'verifications': len(verified), 'verification_history': verified,
            'tool_requests': len(requests), 'tool_requests_by_name': {
                name: sum(x['tool'] == name for x in requests) for name in sorted({x['tool'] for x in requests})},
            'tool_rejections': len(refused), 'rejected_requests': refused,
            'model_attempts': model.get('model_calls', 0),
            'saved_model_requests': len(model_requests), 'saved_model_responses': len(model_responses),
            'model_responses_with_usage': len(model.get('usage', [])),
            'termination_reason': termination, 'model_error': error,
            'task_status': repair.get('task_status', 'INCOMPLETE'),
            'evidence_gaps': inconsistencies,
            'source': 'host RPC acceptance + candidate/verification history; raw model request/response/usage'}


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
    model = repair.get("model") if isinstance(repair.get("model"), dict) else {}
    artifact_root = Path(repair.get("artifact_dir", "")).resolve() if repair.get("artifact_dir") else None
    accepted = sorted(p.stem for p in (artifact_root / "verification-history").glob("candidate-*.py")) if artifact_root and (artifact_root / "verification-history").is_dir() else []
    counts = execution_summary(repair)
    inferred = bool(counts["model_attempts"] or model.get("status") or (artifact_root and (artifact_root / "model-work/model-result.json").is_file()))
    execution_kind = "real-local-model-inference" if inferred else "blocked-before-model-inference"
    termination = repair.get("reason") or model.get("termination_reason") or model.get("status")
    execution_counts = counts
    row = {
        "schema": "credproof.web-live-record/v1",
        "method": "C-agent",
        "execution_kind": execution_kind,
        "project_id": project_id,
        "case_id": case_id,
        "project_config": config_path.name,
        "initial_authority": _authority(initial),
        "diagnosis": {"diagnosis": "模型意见与程序初始证据分开保存；详见模型轨迹。",
                      "initially_leaking": _authority(initial)["confirmed"] == "CONFIRMED_LEAK"},
        "final_validation": final,
        "task": {"task_status": task_status, "reason": repair.get("reason")},
        "model": model,
        "execution_counts": execution_counts,
        "tool_trace": repair.get("tool_trace", []),
        "observations": _observation(initial),
        "candidate_count": len(accepted),
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
    parser.add_argument("--project-id")
    parser.add_argument("--case-id")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--origin-only", action="store_true")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    args.output = args.output.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    _write(args.output / "origin-receipt.json", {
        "schema": "credproof.installed-origin/v1",
        "interpreter": str(Path(sys.executable).resolve()),
        "cwd": str(Path.cwd().resolve()),
        "web_repair": str(Path(__file__).resolve()),
        "agent": str(Path(__import__('credproof_safety.agent', fromlist=['__file__']).__file__).resolve()),
        "package_version": importlib.metadata.version("credproof-safety"),
        "isolated_import": "python -I -m credproof_safety.web_repair",
    })
    if args.origin_only:
        print(json.dumps({"status": "ORIGIN_ONLY"}, ensure_ascii=False))
        return 0
    if not args.project_id or not args.case_id or args.config is None:
        raise SystemExit("--project-id, --case-id and --config are required unless --origin-only is used")
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
