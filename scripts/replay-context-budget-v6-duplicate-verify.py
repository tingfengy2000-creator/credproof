"""Replay v6's unsent request with the duplicate-verify response compacted.

This is a no-model protocol replay.  It starts from the actual v6 request-10
payload, replaces only the redundant ``candidate_already_verified`` response
with the bounded response now produced by the executor, and runs the same
UTF-8 wire budget estimator used by the client.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_pilot.model_client import estimate_input_budget


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.payload.read_text(encoding="utf-8"))
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) <= 11:
        raise SystemExit("v6 payload does not contain the expected verify response")
    old_result = json.loads(messages[11]["content"])
    if old_result.get("reason") != "candidate_already_verified":
        raise SystemExit("unexpected duplicate-verify reason")
    old_report = old_result.get("verification")
    if not isinstance(old_report, dict):
        raise SystemExit("missing duplicate-verify report")

    # The preceding automatic verification already delivered the full bounded
    # report.  A repeated verify call only needs the decision-bearing fields;
    # the complete report remains in the host audit artifact.
    compact_report = {
        key: old_report[key]
        for key in (
            "schema", "object_id", "verdict", "reason", "required_checks",
            "confirmed_failed_checks", "pytest_summary",
        )
        if key in old_report
    }
    compact_result = {
        "status": "REJECTED",
        "reason": "candidate_already_verified",
        "candidate": old_result.get("candidate"),
        "verification": {
            "status": "REJECTED",
            "reason": "candidate_already_verified",
            "candidate": old_result.get("candidate"),
            "report": compact_report,
        },
        "executor_state_relation": "latest_host_state_in_executor_context",
    }

    old_budget = estimate_input_budget(payload, int(payload.get("max_tokens", 1024)))
    replay = json.loads(json.dumps(payload, ensure_ascii=False))
    replay["messages"][11]["content"] = json.dumps(
        compact_result, ensure_ascii=False, separators=(",", ":")
    )
    new_budget = estimate_input_budget(replay, int(replay.get("max_tokens", 1024)))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "reconstructed-next-request.json").write_text(
        json.dumps(replay, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    summary = {
        "schema": "credproof.context-budget-pilot-v6/duplicate-verify-replay/v1",
        "protocol_replay": True,
        "model_request_sent": False,
        "candidate_execution": False,
        "input_source": str(args.payload).replace("\\", "/"),
        "old_unsent_budget": old_budget,
        "new_compacted_budget": new_budget,
        "replacement": {
            "reason": "candidate_already_verified",
            "preserved_candidate": compact_result.get("candidate"),
            "preserved_verdict": compact_report.get("verdict"),
            "preserved_failed_checks": compact_report.get("confirmed_failed_checks", []),
            "removed_duplicate_fields": [
                "readable_paths", "repair_guidance", "scenario_summary",
                "request_summary", "access_summary", "omitted_counts",
            ],
        },
        "assertions": {
            "old_payload_exceeded_input_limit": old_budget["within_context_budget"] is False,
            "new_payload_within_input_limit": new_budget["input_token_upper_bound"] <= new_budget["input_token_limit"],
            "new_payload_within_context_limit": new_budget["within_context_budget"],
            "failure_state_preserved": compact_report.get("verdict") == "FAIL"
            and bool(compact_report.get("confirmed_failed_checks")),
            "no_request_sent": True,
        },
    }
    (args.output_dir / "replay-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(summary["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
