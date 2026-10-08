"""Rebuild v6's next turn through the current client conversion path.

This is a no-model, no-candidate protocol replay.  It starts from the real
model-09 wire request, appends the real NO_CHANGE event and a duplicate
verify_patch response built by the current trusted helper, then runs the
current Qwen-message compactor and Ollama conversion before estimating the
next payload.  It does not call Ollama or execute the candidate.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_pilot.model_client import (compact_messages_for_budget,
                                      estimate_input_budget,
                                      to_ollama_messages)
from credproof_safety.agent import _verification_repeat_summary
from credproof_safety.config import load_config


def oai_to_qwen(payload: dict) -> list[dict]:
    """Convert the recorded Ollama wire messages to Qwen internal messages."""
    result: list[dict] = []
    for item in payload.get("messages", []):
        role = item.get("role")
        if role in {"system", "user"}:
            result.append({"role": role, "content": item.get("content") or ""})
        elif role == "assistant":
            if item.get("content"):
                result.append({"role": "assistant", "content": item["content"]})
            for call in item.get("tool_calls") or []:
                result.append({
                    "role": "assistant", "content": "",
                    "function_call": copy.deepcopy(call["function"]),
                    "extra": {"function_id": call["id"]},
                })
        elif role == "tool":
            result.append({
                "role": "function", "content": item.get("content") or "",
                "extra": {"function_id": item["tool_call_id"]},
            })
        else:
            raise ValueError(f"unsupported recorded role: {role!r}")
    return result


def replace_current_text(payload: dict) -> None:
    """Apply only the current prompt/tool wording to the recorded payload."""
    old = "Submit a minimal patch, verify it, and on FAIL use the actual failed checks and "
    new = "Submit a minimal patch; the executor automatically verifies it. On FAIL use the actual failed checks and "
    for item in payload["messages"]:
        if isinstance(item.get("content"), str):
            item["content"] = item["content"].replace(old, new)
            item["content"] = item["content"].replace(
                "submit_patch (program automatically verifies)",
                "submit_patch (program automatically verifies; do not call verify_patch again)",
            )
            if item["role"] == "system" and "do not call verify_patch after submit_patch" not in item["content"]:
                item["content"] += " Do not call verify_patch after submit_patch; the executor has already performed that verification."
    for tool in payload.get("tools", []):
        function = tool.get("function", {})
        if function.get("name") == "verify_patch":
            function["description"] = (
                "Compatibility-only entry. submit_patch already runs trusted verification; "
                "do not call this again for an accepted candidate. A repeated call is rejected."
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model09_request", type=Path)
    parser.add_argument("no_change_response", type=Path)
    parser.add_argument("duplicate_report", type=Path)
    parser.add_argument("duplicate_state", type=Path)
    parser.add_argument("--config", type=Path,
                        default=ROOT / "examples/material_assistant/credproof.toml")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    wire = json.loads(args.model09_request.read_text(encoding="utf-8"))
    # model-09-request is already the real request after the NO_CHANGE event;
    # do not append that event a second time.  The optional file is retained as
    # a provenance check for callers that want to assert the source response.
    no_change = json.loads(args.no_change_response.read_text(encoding="utf-8"))
    report = json.loads(args.duplicate_report.read_text(encoding="utf-8"))
    state_document = json.loads(args.duplicate_state.read_text(encoding="utf-8"))
    # The recorded duplicate-verify response carries the authoritative state
    # inside its verification object.  Keep that state, rather than wrapping
    # the whole RPC response as if it were an executor_state.
    state = state_document.get("executor_state")
    if not isinstance(state, dict):
        verification = state_document.get("verification")
        state = verification.get("executor_state") if isinstance(verification, dict) else None
    if not isinstance(state, dict):
        raise SystemExit("duplicate verify response has no executor_state")
    config = load_config(args.config)
    candidate_code = None
    for item in wire.get("messages", []):
        for call in item.get("tool_calls") or []:
            if call.get("function", {}).get("name") == "submit_patch":
                candidate_code = json.loads(call["function"]["arguments"]).get("code")
    if not isinstance(candidate_code, str):
        raise SystemExit("candidate-02 source was not found in the recorded request")

    compact_report = _verification_repeat_summary(report, config)
    current_duplicate = {
        "status": "REJECTED",
        "reason": "candidate_already_verified",
        "candidate": 2,
        "verification": {
            "status": "REJECTED",
            "reason": "candidate_already_verified",
            "candidate": 2,
            "report": compact_report,
        },
        "executor_state": state,
    }
    internal = oai_to_qwen(wire)
    internal.extend([
        {"role": "assistant", "content": "", "function_call": {
            "name": "verify_patch", "arguments": "{}",
        }, "extra": {"function_id": "replay-verify-current"}},
        {"role": "function", "content": json.dumps(current_duplicate, ensure_ascii=False),
         "extra": {"function_id": "replay-verify-current"}},
    ])
    compacted = compact_messages_for_budget(internal)
    next_messages = to_ollama_messages(compacted)
    next_payload = copy.deepcopy(wire)
    next_payload["messages"] = next_messages
    replace_current_text(next_payload)
    budget = estimate_input_budget(next_payload, int(next_payload.get("max_tokens", 1024)))
    encoded = json.dumps(next_payload, ensure_ascii=False)
    text = encoded
    def _tool_call_rows(messages):
        rows = []
        for message in messages:
            if message.get("role") != "assistant":
                continue
            for call in message.get("tool_calls") or []:
                fn = call.get("function") or {}
                rows.append((call.get("id"), fn.get("name"), fn.get("arguments") or ""))
        return rows

    call_rows = _tool_call_rows(next_messages)
    source_visible = False
    for _, name, arguments in call_rows:
        if name != "submit_patch" or not isinstance(arguments, str):
            continue
        try:
            decoded_args = json.loads(arguments)
        except (TypeError, ValueError):
            decoded_args = {}
        if isinstance(decoded_args, dict) and decoded_args.get("code") == candidate_code:
            source_visible = True
    tool_results = {
        item.get("tool_call_id"): item.get("content", "")
        for item in next_messages if item.get("role") == "tool"
    }
    paired_ids = {ident for ident, _, _ in call_rows} == set(tool_results)
    joined = json.dumps(next_messages, ensure_ascii=False)
    parsed_tool_values = []
    for item in next_messages:
        if item.get("role") != "tool":
            continue
        try:
            value = json.loads(item.get("content") or "{}")
        except (TypeError, ValueError):
            value = {}
        if isinstance(value, dict):
            parsed_tool_values.append(value)
    trusted_states = []
    for item in next_messages:
        if item.get("role") != "user" or not isinstance(item.get("content"), str):
            continue
        try:
            value = json.loads(item["content"])
        except (TypeError, ValueError):
            value = {}
        state_value = value.get("executor_state") if isinstance(value, dict) else None
        if isinstance(state_value, dict):
            trusted_states.append(state_value)
    checks = {
        "model_request_sent": False,
        "candidate_execution": False,
        "current_candidate_source_visible": bool(candidate_code and source_visible),
        "required_test_visible": "tests/test_business.py" in text,
        "candidate_fail_visible": any(
            value.get("verdict") == "FAIL" or
            isinstance(value.get("verification"), dict) and value["verification"].get("verdict") == "FAIL" or
            isinstance(value.get("verification"), dict) and isinstance(value["verification"].get("report"), dict)
            and value["verification"]["report"].get("verdict") == "FAIL"
            for value in parsed_tool_values
        ),
        "no_change_visible": "NO_CHANGE" in text,
        "duplicate_verify_rejected_visible": "candidate_already_verified" in text,
        "rejected_status_preserved": any(value.get("status") == "REJECTED" for value in parsed_tool_values),
        "latest_tool_pair_visible": "replay-verify-current" in text,
        "latest_state_visible": any(
            state_value.get("current_candidate") == 2 and
            state_value.get("remaining_tool_calls") == 2 and
            state_value.get("last_verification_verdict") == "FAIL"
            for state_value in trusted_states
        ),
        "tool_call_result_ids_paired": paired_ids,
        "within_input_limit": budget["input_token_upper_bound"] <= budget["input_token_limit"],
        "within_context_limit": budget["within_context_budget"],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "current-client-next-request.json").write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "schema": "credproof.context-budget-pilot-v6/current-client-continuation/v1",
        "protocol_replay": True,
        "model_request_sent": False,
        "candidate_execution": False,
        "source_model_request": str(args.model09_request).replace("\\", "/"),
        "source_no_change_response": str(args.no_change_response).replace("\\", "/"),
        "source_duplicate_report": str(args.duplicate_report).replace("\\", "/"),
        "compactor": "agent_pilot.model_client.compact_messages_for_budget",
        "ollama_conversion": "agent_pilot.model_client.to_ollama_messages",
        "duplicate_response_builder": "credproof_safety.agent._verification_repeat_summary",
        "input_messages_before_compaction": len(internal),
        "output_messages_after_compaction": len(next_messages),
        "budget": budget,
        "checks": checks,
        "notes": "A protocol replay is not model usage and does not execute a candidate; the v6 live run remains unchanged.",
    }
    (args.output_dir / "current-client-continuation-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    # These two guards are expected false for a protocol-only replay.  Only
    # the preservation, pairing, and budget assertions determine preflight
    # success; sending a model request or executing a candidate would be a
    # replay violation.
    positive_checks = [key for key in checks
                       if key not in {"model_request_sent", "candidate_execution"}]
    guard_checks = not checks["model_request_sent"] and not checks["candidate_execution"]
    return 0 if guard_checks and all(checks[key] for key in positive_checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
