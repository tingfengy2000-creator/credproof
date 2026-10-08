"""Replay the v7 revision-stage evidence without contacting the model.

This is a protocol/data-integrity check.  It reads the saved Ollama wire
requests and responses, checks that the accepted candidate and trusted FAIL
facts reached the model, and checks the current executor's phase gates.  It
does not execute the candidate or count as a model repair run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credproof_safety.agent import _phase_rejection


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(value: str) -> str:
    return hashlib.sha256(value.replace("\r\n", "\n").replace("\r", "\n").encode()).hexdigest()


def tool_pairs(request: dict) -> list[dict]:
    by_id = {}
    for item in request.get("messages", []):
        if item.get("role") == "tool":
            by_id[item.get("tool_call_id")] = item
    pairs = []
    for item in request.get("messages", []):
        if item.get("role") != "assistant":
            continue
        for call in item.get("tool_calls", []):
            result = by_id.get(call.get("id"))
            pairs.append({"call_id": call.get("id"), "name": call.get("function", {}).get("name"),
                          "arguments": call.get("function", {}).get("arguments"),
                          "result": json.loads(result["content"]) if result else None})
    return pairs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, default=Path(
        "docs/reusable-tool-safety/acceptance/20261007-return-redirect/"
        "context-budget-pilot-v7/formal-p01-model-result-artifacts/model-work/model-trace"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    requests = {n: read(args.trace / f"model-{n:02d}-request.json") for n in (7, 8, 9)}
    responses = {n: read(args.trace / f"model-{n:02d}-response.json") for n in (7, 8, 9)}
    pairs = {n: tool_pairs(requests[n]) for n in requests}

    accepted = next(pair for pair in pairs[7]
                    if pair["result"] and pair["result"].get("status") == "ACCEPTED_FOR_VERIFICATION")
    report = accepted["result"]["verification"]["report"]
    state_by_request = {}
    for n, request in requests.items():
        contexts = [m["content"] for m in request.get("messages", [])
                    if m.get("role") == "user" and "executor-context/v1" in m.get("content", "")]
        state_by_request[n] = json.loads(contexts[-1]) if contexts else None

    read_results = {}
    for n in (8, 9):
        pair = next(pair for pair in pairs[n]
                    if pair["name"] == "read_code" and pair["result"] and
                    pair["result"].get("status") == "OK" and pair["result"].get("path") == "tool.py")
        read_results[n] = {
            "call_id": pair["call_id"],
            "path": pair["result"].get("path"),
            "code_sha256": sha(pair["result"].get("code", "")),
            "code_bytes": len(pair["result"].get("code", "").encode("utf-8")),
        }

    accepted_hash = accepted["result"].get("candidate_sha256")
    state8 = state_by_request[8]["executor_state"]
    state9 = state_by_request[9]["executor_state"]
    required = {"tool.py", "tests/test_business.py"}
    gate_kwargs = dict(evidence_ready=True, read_paths=required,
                       required_read_paths=required, accepted_candidates=2,
                       last_verified_candidate=2, last_verification_verdict="FAIL")

    checks = {
        "candidate_and_fail_in_request_7": (
            state_by_request[7]["executor_state"]["current_candidate"] == 2
            and state_by_request[7]["executor_state"]["last_verification_verdict"] == "FAIL"
            and accepted_hash == state_by_request[7]["executor_state"]["current_candidate_sha256"]
            and report.get("confirmed_failed_checks")
            and report.get("violation_facts", {}).get("forbidden_file_attempts") == 1
            and report.get("violation_facts", {}).get("forbidden_service_receipts") == 1
        ),
        "candidate_source_reaches_request_8": (
            read_results[8]["code_sha256"] == accepted_hash
            and state8["current_candidate_sha256"] == accepted_hash
        ),
        "candidate_source_reaches_request_9": (
            read_results[9]["code_sha256"] == accepted_hash
            and state9["current_candidate_sha256"] == accepted_hash
        ),
        "latest_reads_have_paired_returns": all(
            pair["result"] is not None for n in (8, 9) for pair in pairs[n]
            if pair["name"] == "read_code"),
        "revision_read_is_rejected_by_current_executor":
            _phase_rejection("read_code", **gate_kwargs) == "revision_source_already_current",
        "revision_evidence_is_rejected_by_current_executor":
            _phase_rejection("get_evidence", **gate_kwargs) == "revision_evidence_already_current",
        "revision_submit_is_allowed": _phase_rejection("submit_patch", **gate_kwargs) is None,
    }
    result = {
        "schema": "credproof.replay.v7-revision-stage/v1",
        "kind": "NO_MODEL_PROTOCOL_REPLAY",
        "source_material": "context-budget-pilot-v7/model-trace/model-07..09",
        "model_contacted": False,
        "candidate_execution": False,
        "candidate": {"number": 2, "sha256": accepted_hash},
        "model_requests": {str(n): {
            "request_bytes": len((args.trace / f"model-{n:02d}-request.json").read_bytes()),
            "response_id": responses[n].get("id"),
            "usage": responses[n].get("usage"),
            "tool_calls": [{"id": p["call_id"], "name": p["name"]} for p in pairs[n]],
        } for n in requests},
        "trusted_failure_facts": {
            "confirmed_failed_checks": report.get("confirmed_failed_checks", []),
            "violation_facts": report.get("violation_facts", {}),
            "pytest_summary": report.get("pytest_summary", {}),
        },
        "read_results": read_results,
        "executor_state": {str(n): state_by_request[n]["executor_state"] for n in requests},
        "checks": checks,
        "all_checks_pass": all(checks.values()),
        "interpretation": "Candidate, failure facts, source read and state were present in v7 requests; the remaining defect was stage guidance/action scheduling, not proven message loss.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["all_checks_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
