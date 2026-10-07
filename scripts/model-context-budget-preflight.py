from __future__ import annotations

"""Protocol-only preflight for the bounded Qwen repair conversation.

This does not contact Ollama or execute a candidate. It uses the same
``to_ollama_messages`` conversion, tool schemas, and ``estimate_input_budget``
used by the live client.  Values without server usage are explicitly marked as
conservative bounds; they are not claimed token measurements.
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
OUT = ACCEPTANCE / "20261007-context-budget-preflight.json"


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
            "tools": schemas}


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
    after_candidate = after_reads + [
        _assistant_calls(("submit_patch", {"code": candidate_code}, "call-preflight-submit"))[0],
        _function("call-preflight-submit", {"status": "ACCEPTED_FOR_VERIFICATION", "candidate": 1}),
        _assistant_calls(("verify_patch", {}, "call-preflight-verify"))[0],
        _function("call-preflight-verify", {"status": "OK", "report": _model_feedback(candidate_report, config)}),
    ]
    after_candidate_payload = _payload(after_candidate, schemas)
    candidate_budget = _budget("after_candidate_failure_feedback", after_candidate_payload, first_prefix)

    stages = [first_budget, reads_budget, candidate_budget]
    record = {
        "schema": "credproof.model-context-budget-preflight/v1",
        "protocol_preflight": True,
        "model_calls": 0,
        "model": MODEL,
        "context_tokens": CONTEXT_TOKENS,
        "max_output_tokens": 1024,
        "serialization": "agent_pilot.model_client._LocalModel._chat_stream + to_ollama_messages",
        "tool_schema_sha256": hashlib.sha256(json.dumps(schemas, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
        "system_prompt_sha256": hashlib.sha256(system.encode()).hexdigest(),
        "initial_context_bytes": len(json.dumps(initial_context, ensure_ascii=False, sort_keys=True).encode()),
        "evidence_context_bytes": len(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()),
        "history_compaction": {
            "before_internal_messages": len(after_candidate),
            "after_wire_messages": len(after_candidate_payload["messages"]),
            "after_wire_roles": [item.get("role") for item in after_candidate_payload["messages"]],
            "reason": "base task plus latest verify pair; executor retains phase state and model can re-read declared files",
        },
        "full_reports": "retained separately; not placed in model-visible compact feedback",
        "stages": stages,
        "all_within_declared_budget": all(item["within_context_budget"] and item["within_wire_limit"] for item in stages),
        "notes": [
            "No Ollama request, candidate execution, or verification occurred during this preflight.",
            "The first-prefix prompt_tokens value is the first request conservative upper bound, not server usage.",
            "Runtime usage will be recorded only from the service response; no bytes-to-token conversion is used.",
            "Candidate failure feedback uses the saved candidate report only to size the next conversation; it is not a new model result.",
        ],
    }
    OUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
