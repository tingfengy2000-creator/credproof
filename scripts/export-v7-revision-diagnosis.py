"""Export a small, structured, non-secret diagnosis of v7 requests 7--9."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_excerpt(value: dict) -> dict:
    out = {k: value[k] for k in (
        "status", "reason", "path", "read_sha256", "candidate", "candidate_sha256",
        "verification_action", "allowed_actions", "original_reason") if k in value}
    verification = value.get("verification")
    if isinstance(verification, dict):
        out["verification"] = {
            k: verification[k] for k in ("status", "candidate", "verification") if k in verification
        }
        report = verification.get("report")
        if isinstance(report, dict):
            out["report"] = {
                k: report[k] for k in ("verdict", "confirmed_failed_checks", "violation_facts",
                                       "pytest_summary", "credential_leaks") if k in report
            }
    state = value.get("executor_state")
    if isinstance(state, dict):
        out["executor_state"] = state
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    index = {
        "schema": "credproof.v7-revision-diagnosis/v1",
        "source": "v7 model trace, requests 7-9",
        "model_contacted_by_exporter": False,
        "omitted_fields": ["full source text", "stdout/stderr", "logs", "raw audit rows",
                            "runtime credentials", "host absolute paths"],
        "omitted_reason": "Candidate source is already a public artifact; the diagnosis retains hashes, sizes, tool IDs, state, and trusted failure facts.",
        "files": {},
    }
    for number in (7, 8, 9):
        request_path = args.trace / f"model-{number:02d}-request.json"
        response_path = args.trace / f"model-{number:02d}-response.json"
        request = load(request_path)
        response = load(response_path)
        calls = []
        tool_results = {}
        for item in request.get("messages", []):
            if item.get("role") == "tool":
                try:
                    tool_results[item.get("tool_call_id")] = json.loads(item.get("content", "{}"))
                except (TypeError, ValueError):
                    tool_results[item.get("tool_call_id")] = {"status": "UNPARSEABLE"}
        for item in request.get("messages", []):
            if item.get("role") != "assistant":
                continue
            for call in item.get("tool_calls", []):
                call_id = call.get("id")
                result = tool_results.get(call_id, {})
                calls.append({"id": call_id, "name": call.get("function", {}).get("name"),
                              "arguments": call.get("function", {}).get("arguments", ""),
                              "result": result_excerpt(result)})
        contexts = []
        for item in request.get("messages", []):
            if item.get("role") == "user" and "executor-context/v1" in item.get("content", ""):
                try:
                    contexts.append(json.loads(item["content"]))
                except (TypeError, ValueError):
                    contexts.append({"status": "UNPARSEABLE"})
        entry = {
            "schema": "credproof.v7-revision-request-excerpt/v1",
            "request_number": number,
            "request_sha256": sha(request_path),
            "request_bytes": request_path.stat().st_size,
            "message_count": len(request.get("messages", [])),
            "tool_calls": calls,
            "latest_executor_context": contexts[-1] if contexts else None,
            "response": {
                "id": response.get("id"), "model": response.get("model"),
                "finish_reason": (response.get("choices") or [{}])[0].get("finish_reason"),
                "usage": response.get("usage"),
                "tool_calls": [
                    {"id": call.get("id"), "name": call.get("function", {}).get("name"),
                     "arguments": call.get("function", {}).get("arguments", "")}
                    for call in ((response.get("choices") or [{}])[0].get("message", {}).get("tool_calls") or [])
                ],
            },
            "response_sha256": sha(response_path),
        }
        filename = f"request-{number:02d}-excerpt.json"
        (args.output / filename).write_text(json.dumps(entry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        index["files"][filename] = {"request_sha256": entry["request_sha256"],
                                     "response_sha256": entry["response_sha256"]}
    (args.output / "diagnosis-index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
