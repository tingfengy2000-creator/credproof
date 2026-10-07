from __future__ import annotations

"""Replay the saved v3 tool sequence through the current message compactor.

This is a protocol check only: it does not contact Ollama, execute a
candidate, or count as a model repair run.  It uses the actual saved request,
responses, and host tool results so the retained call/result IDs and executor
state can be reviewed without trusting a hand-built status fixture.
"""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_pilot.model_client import compact_messages_for_budget, to_ollama_messages

SOURCE = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v3"
TRACE_DIR = SOURCE / "formal-p01-model-result-artifacts/model-work/model-trace"
RESULT = SOURCE / "formal-p01-model-result.json"
OUT = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v4"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def internal_from_wire(items: list[dict]) -> list[dict]:
    messages: list[dict] = []
    for item in items:
        if item.get("role") in {"system", "user"}:
            messages.append({"role": item["role"], "content": item.get("content", "")})
        elif item.get("role") == "assistant":
            for call in item.get("tool_calls", []):
                messages.append({
                    "role": "assistant", "content": "", "function_call": call["function"],
                    "extra": {"function_id": call["id"]},
                })
        elif item.get("role") == "tool":
            messages.append({
                "role": "function", "content": item["content"],
                "extra": {"function_id": item["tool_call_id"]},
            })
    return messages


def call_from_response(number: int) -> dict:
    response = read_json(TRACE_DIR / f"model-{number:02d}-response.json")
    message = response["choices"][0]["message"]
    calls = message.get("tool_calls") or []
    if len(calls) != 1:
        raise AssertionError(f"expected one saved call in model-{number:02d}")
    call = calls[0]
    return {"role": "assistant", "content": "", "function_call": call["function"],
            "extra": {"function_id": call["id"]}}


def result_from_trace(number: int) -> dict:
    record = read_json(RESULT)
    # v3 trace is ordered: model 1 is get_evidence, model 2 is entry read,
    # model 3 is tests read, model 4 is submit, model 5..12 are entry reads.
    return record["tool_trace"][number - 1]["result"]


def wire_digest(value: list[dict]) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def ids(value: list[dict]) -> tuple[list[str], list[str]]:
    calls = [call["id"] for item in value for call in item.get("tool_calls", [])]
    results = [item["tool_call_id"] for item in value if item.get("role") == "tool"]
    return calls, results


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    # model-05 is the last saved stale request: it has the accepted candidate
    # and tests read, but no post-verification tool.py read.
    before_wire = read_json(TRACE_DIR / "model-05-request.json")["messages"]
    current = internal_from_wire(before_wire)
    before_payload = {"messages": before_wire, "source": "saved model-05 request (pre-fix)"}
    (OUT / "payload-before.json").write_text(json.dumps(before_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    snapshots = []
    for number in range(5, 13):
        current.extend([call_from_response(number), {
            "role": "function", "content": json.dumps(result_from_trace(number), ensure_ascii=False),
            "extra": {"function_id": call_from_response(number)["extra"]["function_id"]},
        }])
        compacted = compact_messages_for_budget(current)
        wire = to_ollama_messages(compacted)
        calls, results = ids(wire)
        if calls != results:
            raise AssertionError(f"orphan tool pair after saved read {number}: {calls} != {results}")
        encoded = json.dumps(wire, ensure_ascii=False)
        if "tool.py" not in encoded or "executor_state" not in encoded:
            raise AssertionError(f"fresh tool.py/state missing after saved read {number}")
        if '"verdict": "FAIL"' not in encoded and '\\"verdict\\":\\"FAIL' not in encoded:
            # The exact JSON escaping differs between tool results; the
            # trusted summary must still retain the failed verification.
            if "return_leak" not in encoded and "no_credential_output" not in encoded:
                raise AssertionError(f"failed checks missing after saved read {number}")
        state_values = []
        for item in wire:
            if item.get("role") in {"tool", "user"} and "remaining_tool_calls" in item.get("content", ""):
                try:
                    content = json.loads(item["content"])
                    state = content.get("executor_state", {}) if isinstance(content, dict) else {}
                    if state:
                        state_values.append(state)
                except json.JSONDecodeError:
                    pass
        latest_state = state_values[-1] if state_values else {}
        snapshots.append({
            "saved_read_number": number,
            "wire_sha256": wire_digest(wire),
            "wire_bytes": len(encoded.encode("utf-8")),
            "wire_message_count": len(wire),
            "paired_call_ids": calls,
            "latest_state": latest_state,
            "contains_current_entry_body": any(
                item.get("role") == "tool" and item.get("tool_call_id") == call_from_response(number)["extra"]["function_id"]
                for item in wire
            ),
        })
        if number in {5, 12}:
            (OUT / f"payload-after-read-{number:02d}.json").write_text(
                json.dumps({"messages": wire, "source": f"current compactor after saved read {number}"}, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8")

    if len({item["wire_sha256"] for item in snapshots}) != len(snapshots):
        raise AssertionError("consecutive saved reads still produced identical payloads")
    record = {
        "schema": "credproof.context-sequencing-replay/v1",
        "protocol_replay": True,
        "model_run": "not_run",
        "source_trace": "context-budget-pilot-v3/formal-p01-model-result.json and model-trace/model-05..12",
        "pre_fix": {"request": "model-05-request.json", "omitted_latest_entry_read": True},
        "snapshots": snapshots,
        "assertions": {
            "latest_read_pair_retained": all(item["contains_current_entry_body"] for item in snapshots),
            "paired_tool_ids": True,
            "executor_state_changes_with_host_count": len({item["latest_state"].get("tool_calls_used") for item in snapshots}) == len(snapshots),
            "failed_verification_remains_non_ok": True,
            "same_stale_payload_loop_removed": True,
            "context_budget_not_bypassed": "wire bytes are recorded; live estimator remains authoritative",
        },
        "notes": [
            "This replay does not execute a candidate and is not a model success.",
            "All retained statuses and reasons come from saved host results; no result is synthesized.",
            "Old duplicate reads may be dropped only after the newest full read and executor state are retained.",
        ],
    }
    (OUT / "replay-summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
