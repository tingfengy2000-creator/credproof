from __future__ import annotations

"""Replay the v5 post-NO_CHANGE continuation without Ollama or execution.

The public v5 model summary contains the completed tool conversation, while
model-08-request.json contains the actual system/user wire prefix.  The two
are intentionally joined here so the replay does not mistake the first old
tool pair for the request prefix.  The current compactor then builds the
unsent next request and applies the same conservative budget estimator used by
the live client.
"""

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_pilot.model_client import (
    MAX_REQUEST_BYTES,
    CONTEXT_TOKENS,
    compact_messages_for_budget,
    estimate_input_budget,
    to_ollama_messages,
)


PUBLIC = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v5/public-evidence"
OUT = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect/context-budget-pilot-v5/no-change-dedup"


def _payload(messages: list[dict], wire_template: dict) -> dict:
    return {
        "model": wire_template["model"],
        "messages": to_ollama_messages(compact_messages_for_budget(messages)),
        "stream": wire_template["stream"],
        "temperature": wire_template["temperature"],
        "top_p": wire_template["top_p"],
        "max_tokens": wire_template["max_tokens"],
        "seed": wire_template.get("seed", 0),
        "tools": wire_template["tools"],
    }


def main() -> None:
    summary = json.loads((PUBLIC / "formal-p01-model-summary.json").read_text(encoding="utf-8"))
    wire_template = json.loads((PUBLIC / "model-08-request.json").read_text(encoding="utf-8"))
    completed_messages = summary["model"]["messages"]
    # The summary is a compact internal transcript without the system/user
    # prefix.  Reuse the exact prefix from the real model-08 wire request.
    messages = wire_template["messages"][:2] + completed_messages
    payload = _payload(messages, wire_template)
    serialized = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    budget = estimate_input_budget(payload, payload["max_tokens"], None)
    text = json.dumps(payload, ensure_ascii=False)
    tool_calls = [call["id"] for item in payload["messages"] for call in item.get("tool_calls", [])]
    tool_results = [item.get("tool_call_id") for item in payload["messages"] if item.get("role") == "tool"]
    relation = "source_deduplication" in text and "function.arguments.code" in text
    current_source = "credential_env = os.environ" in text
    no_change = "NO_CHANGE" in text
    state = "executor-context/v1" in text and "current_candidate_sha256" in text
    result = {
        "schema": "credproof.context-budget-pilot-v5-no-change-replay/v1",
        "protocol_replay": True,
        "model_request_sent": False,
        "candidate_execution": False,
        "source": {
            "public_summary": "../public-evidence/formal-p01-model-summary.json",
            "wire_prefix": "../public-evidence/model-08-request.json",
            "source_commit_of_formal_run": summary.get("source_commit"),
            "compactor_under_test": str(Path("agent_pilot/model_client.py")),
        },
        "messages": {
            "completed_internal_messages": len(completed_messages),
            "prefix_messages_reused": 2,
            "wire_messages": len(payload["messages"]),
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "ids_paired": tool_calls == tool_results,
        },
        "budget": {
            **budget,
            "request_sha256": hashlib.sha256(serialized).hexdigest(),
            "request_json_bytes": len(serialized),
            "request_limit_bytes": MAX_REQUEST_BYTES,
            "context_limit_tokens": CONTEXT_TOKENS,
        },
        "preserved": {
            "current_source_body": current_source,
            "source_deduplication_relation": relation,
            "no_change_status_and_reason": no_change,
            "latest_executor_state": state,
            "paired_tool_calls_and_results": tool_calls == tool_results,
        },
        "assertions": {
            "all_payload_limits_pass": bool(budget["within_context_budget"] and budget["within_wire_limit"]),
            "current_state_and_source_fit_together": bool(current_source and relation and state),
            "no_request_sent": True,
        },
        "notes": [
            "The previous v5 formal request-09 stop remains an unsent 15,972-byte payload; this replay is a post-fix derived payload, not a new model result.",
            "The duplicate read body is removed only when the exact same normalized source is retained in the NO_CHANGE submit arguments; the relation is explicit and the source is not hash-only.",
            "The public summary and wire prefix are sanitized evidence; no candidate is executed and no Ollama request is sent.",
        ],
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "reconstructed-next-request.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "replay-summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
