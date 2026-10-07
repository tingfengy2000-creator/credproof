from __future__ import annotations

"""Replay the saved v4 request through the current host message protocol.

This script never contacts Ollama, runs a candidate, or asks the executor to
make a decision. It uses the actual saved model-05 request/response and v4
host state, then replaces only the old repeated-evidence result with the
current deterministic phase guard result. The next-candidate branch is a
message-shape protocol sample using the already saved candidate-02; it is not
an execution or model result.
"""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ACCEPTANCE = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect"
V4 = ACCEPTANCE / "context-budget-pilot-v4"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ACCEPTANCE / "context-budget-pilot-v5"
if OUT.suffix.lower() == ".json":
    OUT = OUT.parent
sys.path.insert(0, str(ROOT))

from agent_pilot.model_client import compact_messages_for_budget, estimate_input_budget, to_ollama_messages
from credproof_safety.agent import _phase_rejection


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def wire_to_internal(messages: list[dict]) -> list[dict]:
    """Convert the saved Ollama wire payload to Qwen-Agent internal records."""
    result = []
    for item in messages:
        role = item.get("role")
        if role in {"system", "user"}:
            result.append({"role": role, "content": item.get("content", "")})
        elif role == "assistant":
            calls = item.get("tool_calls") or []
            if not calls:
                result.append({"role": "assistant", "content": item.get("content", "")})
            for call in calls:
                result.append({
                    "role": "assistant", "content": item.get("content", ""),
                    "function_call": copy.deepcopy(call.get("function", {})),
                    "extra": {"function_id": call.get("id")},
                })
        elif role == "tool":
            result.append({
                "role": "function", "content": item.get("content", ""),
                "extra": {"function_id": item.get("tool_call_id")},
            })
        else:
            raise ValueError(f"unsupported saved wire role: {role!r}")
    return result


def response_call(response: dict) -> dict:
    message = response["choices"][0]["message"]
    call = message["tool_calls"][0]
    return {
        "role": "assistant", "content": message.get("content", ""),
        "function_call": copy.deepcopy(call["function"]),
        "extra": {"function_id": call["id"]},
    }


def payload_from_internal(messages: list[dict], template: dict) -> tuple[dict, list[dict]]:
    compacted = compact_messages_for_budget(messages)
    payload = {key: copy.deepcopy(value) for key, value in template.items() if key != "messages"}
    payload["messages"] = to_ollama_messages(compacted)
    return payload, compacted


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = load_json(V4 / "formal-p01-model-result.json")
    request05 = load_json(V4 / "public-evidence/model-05-request.json")
    response05 = load_json(V4 / "public-evidence/model-05-response.json")
    actual_trace = raw["tool_trace"]
    prior_state = copy.deepcopy(actual_trace[4]["result"]["executor_state"])
    current_reason = _phase_rejection(
        "get_evidence", evidence_ready=True,
        read_paths={"tool.py", "tests/test_business.py"},
        required_read_paths={"tool.py", "tests/test_business.py"},
        accepted_candidates=1,
    )
    if current_reason != "evidence_already_current":
        raise AssertionError(current_reason)

    # v4 model-05 is the real saved request immediately before the repeated
    # get_evidence response. Preserve its exact payload as the first artifact.
    (OUT / "payload-before-repeat.json").write_text(
        json.dumps(request05, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    messages = wire_to_internal(request05["messages"])
    messages.append(response_call(response05))
    current_state = copy.deepcopy(prior_state)
    current_state.update({
        "tool_calls_used": 6,
        "remaining_tool_calls": 6,
        "next_action": "review_verification_and_submit_new_candidate_or_stop",
        "phase": "candidate_verified",
    })
    current_result = {
        "status": "REJECTED",
        "reason": current_reason,
        "executor_state": current_state,
    }
    messages.append({
        "role": "function",
        "content": json.dumps(current_result, ensure_ascii=False),
        "extra": {"function_id": response05["choices"][0]["message"]["tool_calls"][0]["id"]},
    })
    template = {key: copy.deepcopy(value) for key, value in request05.items() if key != "messages"}
    after_payload, after_internal = payload_from_internal(messages, request05)
    (OUT / "payload-after-current-rejection.json").write_text(
        json.dumps(after_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # A legal next candidate message shape, based on the already saved
    # candidate-02. It is a protocol sample only; no verification is run here.
    candidate2 = (ACCEPTANCE / "candidate02.py").read_text(encoding="utf-8")
    candidate2_sha = hashlib.sha256(candidate2.replace("\r\n", "\n").encode()).hexdigest()
    candidate2_report = load_json(ACCEPTANCE / "candidate02-report.json")
    messages2 = copy.deepcopy(after_internal)
    messages2.extend([
        {"role": "assistant", "content": "", "function_call": {
            "name": "submit_patch", "arguments": json.dumps({"code": candidate2}, ensure_ascii=False)},
            "extra": {"function_id": "protocol-candidate-02-submit"}},
        {"role": "function", "content": json.dumps({
            "status": "ACCEPTED_FOR_VERIFICATION", "candidate": 2,
            "candidate_sha256": candidate2_sha,
            "verification_action": "program_auto_verify",
            "verification": {"status": "PROTOCOL_SAMPLE", "candidate": 2,
                             "report": {"verdict": candidate2_report.get("verdict"),
                                        "failed_checks": candidate2_report.get("failed_checks", [])}},
            "executor_state": {
                **current_state,
                "phase": "candidate_verified", "current_candidate": 2,
                "current_candidate_sha256": candidate2_sha,
                "last_verified_candidate": 2, "last_verification_verdict": "FAIL",
                "tool_calls_used": 7, "remaining_tool_calls": 5,
                "candidates_accepted": 2, "remaining_candidates": 1,
                "verifications_run": 2, "remaining_verifications": 1,
            },
            "protocol_sample": True,
            "execution": "not_run",
        }, ensure_ascii=False), "extra": {"function_id": "protocol-candidate-02-submit"}},
    ])
    next_payload, _ = payload_from_internal(messages2, request05)
    (OUT / "payload-after-next-candidate-sample.json").write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Measure both the real before/after branch and the bounded next-candidate
    # protocol sample. The prior prompt count is the actual model-05 service
    # usage, not a byte/token conversion.
    previous = {"payload": request05, "prompt_tokens": response05["usage"]["prompt_tokens"], "call_id": response05["id"]}
    before_budget = estimate_input_budget(request05, request05.get("max_tokens", 1024), None)
    after_budget = estimate_input_budget(after_payload, after_payload.get("max_tokens", 1024), previous)
    next_budget = estimate_input_budget(next_payload, next_payload.get("max_tokens", 1024), previous)
    all_budget = all(x["within_context_budget"] and x["within_wire_limit"]
                     for x in (before_budget, after_budget, next_budget))

    def ids_and_state(payload):
        calls = [c["id"] for m in payload["messages"] for c in m.get("tool_calls", [])]
        results = [m.get("tool_call_id") for m in payload["messages"] if m.get("role") == "tool"]
        text = json.dumps(payload, ensure_ascii=False)
        return {
            "tool_call_ids": calls, "tool_result_ids": results,
            "ids_paired": calls == results,
            "has_current_source": "credential_env = os.environ" in text,
            "has_required_test": "test_normal_business_result_contains_no_credential" in text,
            "has_failure": "FAIL" in text,
            "has_current_rejection": "evidence_already_current" in text,
            "has_latest_executor_state": "remaining_tool_calls" in text and "current_candidate" in text,
            "wire_bytes": len(json.dumps(payload, ensure_ascii=False).encode("utf-8")),
            "wire_messages": len(payload["messages"]),
        }

    summary = {
        "schema": "credproof.context-budget-v4-replay/v1",
        "protocol_replay": True, "model_run": False, "candidate_execution": False,
        "source": {
            "v4_result": "context-budget-pilot-v4/formal-p01-model-result.json",
            "real_request": "context-budget-pilot-v4/public-evidence/model-05-request.json",
            "real_response": "context-budget-pilot-v4/public-evidence/model-05-response.json",
            "real_tool_trace_count": len(actual_trace),
        },
        "current_executor_return": {
            "status": current_result["status"], "reason": current_result["reason"],
            "state_source": "v4 tool_trace[4] state plus host tool count 6",
            "old_saved_result_status": actual_trace[5]["result"].get("status"),
            "old_saved_result_not_reused": True,
        },
        "stages": {
            "before_repeat": {"payload": "payload-before-repeat.json", "budget": before_budget,
                              "wire": ids_and_state(request05)},
            "after_current_rejection": {"payload": "payload-after-current-rejection.json", "budget": after_budget,
                                         "wire": ids_and_state(after_payload)},
            "after_next_candidate_protocol_sample": {"payload": "payload-after-next-candidate-sample.json", "budget": next_budget,
                                                       "wire": ids_and_state(next_payload),
                                                       "candidate_sha256": candidate2_sha,
                                                       "execution": "not_run"},
        },
        "assertions": {
            "current_read_and_candidate_preserved": ids_and_state(after_payload)["has_current_source"],
            "required_test_preserved": ids_and_state(after_payload)["has_required_test"],
            "failure_and_rejection_preserved": ids_and_state(after_payload)["has_failure"] and ids_and_state(after_payload)["has_current_rejection"],
            "latest_state_preserved": ids_and_state(after_payload)["has_latest_executor_state"],
            "tool_ids_paired": ids_and_state(after_payload)["ids_paired"],
            "all_payloads_within_budget": all_budget,
            "next_candidate_state_is_distinct": ids_and_state(next_payload)["has_current_source"] and candidate2_sha != prior_state["current_candidate_sha256"],
        },
        "notes": [
            "The repeated get_evidence result is recomputed by the current phase guard; the historical v4 OK is retained only as an old fact.",
            "The candidate-02 branch is a protocol sample from an existing saved candidate and is not executed or counted as a model result.",
            "Full raw audit history remains in the local v4 artifact; this replay publishes only structured payloads and derived facts.",
        ],
    }
    (OUT / "replay-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
