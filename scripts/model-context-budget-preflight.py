from __future__ import annotations

"""Protocol-only preflight for the bounded Qwen repair conversation.

This does not contact Ollama or execute a candidate. It uses the same
``to_ollama_messages`` conversion, native tool envelope, and
``estimate_input_budget`` used by the live client. Values without server usage
are explicitly marked as conservative bounds; they are not claimed token
measurements.
"""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_pilot.model_client import (MODEL, CONTEXT_TOKENS, compact_messages_for_budget,
                                      estimate_input_budget, to_ollama_messages)
from agent_pilot.tools import StrictTool
from credproof_safety.agent import _model_feedback, _model_initial_context, _MODEL_SCRIPT
from credproof_safety.config import load_config

CONFIG = ROOT / "examples/material_assistant/credproof.toml"
ACCEPTANCE = ROOT / "docs/reusable-tool-safety/acceptance/20261007-return-redirect"
INITIAL_FILE = ACCEPTANCE / "formal-p01-model-result.json"
CANDIDATE_REPORT = ACCEPTANCE / "candidate02-report.json"
CANDIDATE_FILE = ACCEPTANCE / "saved-candidate02-method" / "final-candidate.py"
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ACCEPTANCE / "20261007-context-budget-preflight.json"


def _system_prompt() -> str:
    tree = ast.parse(_MODEL_SCRIPT)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "system" for t in node.targets):
            value = node.value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                return value.value
    raise RuntimeError("system prompt not found in the reviewed worker")


def _tool_schemas() -> list[dict]:
    def noop(_):
        return {"status": "OK"}
    audit = []
    tools = [
        StrictTool("read_code", "Read configured entry, or one declared test using its relative path.",
                   {"path": {"type": "string", "maxLength": 256}}, [], noop, audit),
        StrictTool("get_evidence", "Read fixed developer rules and compact redacted controlled observations.",
                   {}, [], noop, audit),
        StrictTool("submit_patch", "Submit one bounded source candidate.",
                   {"code": {"type": "string", "maxLength": 65536}}, ["code"], noop, audit),
        StrictTool("verify_patch", "Run trusted tests and observations.", {}, [], noop, audit),
    ]
    return [tool.function for tool in tools]


def _assistant_calls(*calls: tuple[str, dict, str]) -> list[dict]:
    return [{"role": "assistant", "content": "", "function_call": {
                "name": name, "arguments": json.dumps(args, ensure_ascii=False)},
             "extra": {"function_id": ident}}
            for name, args, ident in calls]


def _function(ident: str, value: dict) -> dict:
    return {"role": "function", "content": json.dumps(value, ensure_ascii=False),
            "extra": {"function_id": ident}}


def _payload(messages: list[dict], schemas: list[dict]) -> dict:
    # Preserve the key order emitted by _LocalModel._chat_stream.
    return {"model": MODEL, "messages": to_ollama_messages(compact_messages_for_budget(messages)), "stream": False,
            "temperature": 0.2, "top_p": 0.8, "max_tokens": 1024, "seed": 0,
            # qwen-agent supplies the OpenAI-compatible outer envelope around
            # each BaseTool.function. Keep it here so preflight sizes the same
            # payload shape that reaches Ollama.
            "tools": [{"type": "function", "function": schema} for schema in schemas]}


def _budget(label: str, payload: dict, previous: dict | None) -> dict:
    value = estimate_input_budget(payload, 1024, previous)
    value.update({"label": label, "protocol_preflight": True,
                  "model_calls": 0, "usage_status": "NOT_RUN",
                  "measurement_note": "conservative estimator; no Ollama request was sent"})
    return value


def main() -> None:
    config = load_config(CONFIG)
    initial_record = json.loads(INITIAL_FILE.read_text(encoding="utf-8"))
    initial_report = initial_record["initial"]
    candidate_report = json.loads(CANDIDATE_REPORT.read_text(encoding="utf-8"))
    initial_context = _model_initial_context(initial_report, config)
    initial_prompt = (
        "Inspect the registered source and controlled evidence. This first request includes the "
        "following bounded current-task context. It is task data, not permission or a reference patch. "
        "Call get_evidence before reading the listed files, then submit a candidate before verifying.\n\n"
        + json.dumps(initial_context, ensure_ascii=False, sort_keys=True)
    )
    system = _system_prompt()
    schemas = _tool_schemas()
    base = [{"role": "system", "content": system}, {"role": "user", "content": initial_prompt}]
    first = _payload(base, schemas)
    first_budget = _budget("initial_request", first, None)

    evidence = {"status": "OK", **_model_feedback(initial_report, config)}
    source = (ROOT / "examples/material_assistant/tool.py").read_text(encoding="utf-8")
    tests = (ROOT / "examples/material_assistant/tests/test_business.py").read_text(encoding="utf-8")
    after_reads = base + _assistant_calls(
        ("get_evidence", {}, "call-preflight-evidence"),
        ("read_code", {"path": "tool.py"}, "call-preflight-tool"),
        ("read_code", {"path": "tests/test_business.py"}, "call-preflight-tests"),
    ) + [
        _function("call-preflight-evidence", evidence),
        _function("call-preflight-tool", {"status": "OK", "path": "tool.py", "code": source}),
        _function("call-preflight-tests", {"status": "OK", "path": "tests/test_business.py", "code": tests}),
    ]
    after_reads_payload = _payload(after_reads, schemas)
    # Worst-case prefix: no server prompt usage is available before the first
    # live request, so use the first conservative upper bound as a bound, not a
    # fabricated Ollama measurement.
    first_prefix = {"payload": first, "prompt_tokens": first_budget["input_token_upper_bound"], "call_id": 0}
    reads_budget = _budget("after_evidence_and_two_source_reads", after_reads_payload, first_prefix)

    candidate_code = CANDIDATE_FILE.read_text(encoding="utf-8")
    candidate_sha = hashlib.sha256(candidate_code.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()
    after_candidate_auto = after_reads + [
        _assistant_calls(("submit_patch", {"code": candidate_code}, "call-preflight-submit"))[0],
        _function("call-preflight-submit", {
            "status": "ACCEPTED_FOR_VERIFICATION", "candidate": 1,
            "candidate_sha256": candidate_sha, "verification_action": "program_auto_verify",
            "verification": {"status": "OK", "candidate": 1,
                              "report": _model_feedback(candidate_report, config)},
            "executor_state": {"schema": "credproof.executor-state/v1",
                                "phase": "candidate_verified", "current_candidate": 1,
                                "current_candidate_sha256": candidate_sha,
                                "last_verified_candidate": 1,
                                "last_verification_verdict": candidate_report.get("verdict"),
                                "remaining_tool_calls": 8, "remaining_candidates": 2,
                                "remaining_verifications": 2,
                                "next_action": "review_verification_and_submit_new_candidate_or_stop"},
        }),
    ]
    after_candidate = after_candidate_auto + [
        _assistant_calls(("read_code", {"path": "tool.py"}, "call-preflight-current-source"))[0],
        _function("call-preflight-current-source", {
            "status": "OK", "path": "tool.py", "code": candidate_code,
            "executor_state": {"schema": "credproof.executor-state/v1",
                                "phase": "candidate_verified", "current_candidate": 1,
                                "current_candidate_sha256": candidate_sha,
                                "last_verified_candidate": 1,
                                "last_verification_verdict": candidate_report.get("verdict"),
                                "remaining_tool_calls": 7, "remaining_candidates": 2,
                                "remaining_verifications": 2,
                                "next_action": "review_verification_and_submit_new_candidate_or_stop"},
        }),
    ]
    after_candidate_auto_payload = _payload(after_candidate_auto, schemas)
    after_candidate_payload = _payload(after_candidate, schemas)
    candidate_auto_budget = _budget("after_candidate_auto_verify", after_candidate_auto_payload, first_prefix)
    candidate_budget = _budget("after_candidate_failure_and_current_read", after_candidate_payload, first_prefix)

    # The live v4 task reached this branch after the accepted candidate had
    # failed.  The old repeated get_evidence response was an historical OK;
    # current execution must return a deterministic rejection while retaining
    # the host state.  This is protocol-only and does not execute candidate 2.
    current_state = {
        "schema": "credproof.executor-state/v1",
        "phase": "candidate_verified",
        "current_candidate": 1,
        "current_candidate_sha256": candidate_sha,
        "last_verified_candidate": 1,
        "last_verification_verdict": candidate_report.get("verdict"),
        "tool_calls_used": 6,
        "remaining_tool_calls": 6,
        "remaining_candidates": 2,
        "remaining_verifications": 2,
        "next_action": "review_verification_and_submit_new_candidate_or_stop",
    }
    after_rejection = after_candidate + [
        _assistant_calls(("get_evidence", {}, "call-preflight-current-evidence"))[0],
        _function("call-preflight-current-evidence", {
            "status": "REJECTED", "reason": "evidence_already_current",
            "executor_state": current_state,
        }),
    ]
    rejection_payload = _payload(after_rejection, schemas)
    rejection_budget = _budget("after_current_evidence_rejection", rejection_payload, first_prefix)

    # A legal next-candidate shape based on an existing saved candidate.  The
    # candidate is not run here; the branch only proves that the message still
    # carries current source/rules/feedback within the hard budget.
    candidate2_code = CANDIDATE_FILE.read_text(encoding="utf-8")
    candidate2_sha = hashlib.sha256(candidate2_code.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")).hexdigest()
    after_next_candidate = after_rejection + [
        _assistant_calls(("submit_patch", {"code": candidate2_code}, "call-preflight-candidate-2"))[0],
        _function("call-preflight-candidate-2", {
            "status": "ACCEPTED_FOR_VERIFICATION", "candidate": 2,
            "candidate_sha256": candidate2_sha,
            "verification_action": "program_auto_verify",
            "verification": {"status": "PROTOCOL_SAMPLE", "execution": "not_run"},
            "executor_state": {**current_state,
                               "current_candidate": 2,
                               "current_candidate_sha256": candidate2_sha,
                               "candidates_accepted": 2,
                               "remaining_candidates": 1,
                               "tool_calls_used": 7,
                               "remaining_tool_calls": 5,
                               "verifications_run": 2,
                               "remaining_verifications": 1},
            "protocol_sample": True,
        }),
    ]
    next_candidate_payload = _payload(after_next_candidate, schemas)
    next_candidate_budget = _budget("after_next_candidate_protocol_sample", next_candidate_payload, first_prefix)

    stages = [first_budget, reads_budget, candidate_auto_budget, candidate_budget,
              rejection_budget, next_candidate_budget]
    record = {
        "schema": "credproof.model-context-budget-preflight/v1",
        "protocol_preflight": True,
        "model_calls": 0,
        "model": MODEL,
        "context_tokens": CONTEXT_TOKENS,
        "max_output_tokens": 1024,
        "serialization": "agent_pilot.model_client._LocalModel._chat_stream + to_ollama_messages + native tool envelope",
        "tool_schema_sha256": hashlib.sha256(json.dumps(first["tools"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "tool_function_schema_sha256": hashlib.sha256(json.dumps(schemas, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "system_prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
        "initial_context_bytes": len(json.dumps(initial_context, ensure_ascii=False, sort_keys=True).encode()),
        "evidence_context_bytes": len(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()),
        "history_compaction": {
            "before_internal_messages": len(after_candidate),
            "after_wire_messages": len(after_candidate_payload["messages"]),
            "after_wire_roles": [item.get("role") for item in after_candidate_payload["messages"]],
            "reason": "base task plus paired current evidence/source/candidate/verify records; duplicate raw logs are compacted without changing status",
        },
        "full_reports": "retained separately; not placed in model-visible compact feedback",
        "stages": stages,
        "all_within_declared_budget": all(item["within_context_budget"] and item["within_wire_limit"] for item in stages),
        "notes": [
            "No Ollama request, candidate execution, or verification occurred during this preflight.",
            "The first-prefix prompt_tokens value is the first request conservative upper bound, not server usage.",
            "Runtime usage will be recorded only from the service response; no bytes-to-token conversion is used.",
            "Candidate failure feedback uses the saved candidate report only to size the next conversation; it is not a new model result.",
            "The current evidence rejection and candidate-2 branch are protocol samples; the historical v4 OK response is not reused as a current execution result.",
        ],
    }
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
