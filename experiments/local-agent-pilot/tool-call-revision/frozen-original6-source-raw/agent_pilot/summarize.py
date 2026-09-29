"""Read recorded JSON only; never import/execute candidates or start a model.

Usage: python -m agent_pilot.summarize --records EXISTING_RUN --output NEW_FOLDER
Outputs are descriptive evidence tables, not automated judgments of reasoning.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parsed(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (ValueError, TypeError):
            return None
    return value


def same(left, right):
    return json.dumps(left, sort_keys=True, ensure_ascii=False) == json.dumps(right, sort_keys=True, ensure_ascii=False)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def annotate_actions(row, folder):
    """Attach originating model call and native tool ID using recorded journals."""
    requests, last_call = [], None
    journal = folder / "model/events.jsonl"
    if journal.is_file():
        for line in journal.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event") == "model_response":
                last_call = event.get("call_id")
            if event.get("event") == "tool_request":
                requests.append({"tool": event.get("name"), "arguments": parsed(event.get("arguments")),
                                 "originating_model_call": last_call})
    cursor, actions = 0, []
    for index, item in enumerate(row.get("tool_trace", []), 1):
        arguments, result = parsed(item.get("arguments")), parsed(item.get("result"))
        action = {"trace_index": index, "tool": item.get("tool"),
                  "arguments": arguments if isinstance(arguments, dict) else {},
                  "result": result if isinstance(result, dict) else {},
                  "originating_model_call": None, "native_tool_ids": []}
        for position in range(cursor, len(requests)):
            event = requests[position]
            if event["tool"] == action["tool"] and same(event["arguments"], action["arguments"]):
                action["originating_model_call"] = event["originating_model_call"]
                cursor = position + 1
                break
        call = action["originating_model_call"]
        response_path = folder / f"model/model-{call:02d}-response.json" if isinstance(call, int) else None
        if response_path and response_path.is_file():
            response = read_json(response_path)
            for choice in response.get("choices", []):
                for tool in choice.get("message", {}).get("tool_calls") or []:
                    fn = tool.get("function", {})
                    if fn.get("name") == action["tool"] and same(parsed(fn.get("arguments")), action["arguments"]):
                        action["native_tool_ids"].append(tool.get("id"))
        actions.append(action)
    return actions


def feedback_in_request(feedback, later, folder):
    """A later list position alone does not prove the model received feedback."""
    before, after = feedback["originating_model_call"], later["originating_model_call"]
    if not isinstance(before, int) or not isinstance(after, int) or after <= before:
        return False
    path = folder / f"model/model-{after:02d}-request.json"
    if not path.is_file() or not feedback["native_tool_ids"]:
        return False
    return any(message.get("role") == "tool"
               and message.get("tool_call_id") in feedback["native_tool_ids"]
               and same(parsed(message.get("content")), feedback["result"])
               for message in read_json(path).get("messages", []))


def score(entry, labels, run):
    case, row = entry["case"], entry["result"]
    method = entry.get("method", row["method"])
    folder = run / case / method
    actions = annotate_actions(row, folder)
    model = row.get("model")
    configuration = None
    journal_path = folder / "model/events.jsonl"
    if journal_path.is_file():
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event") == "client_created":
                fields = ("model", "max_model_calls", "max_output_tokens", "seed", "request_timeout_s",
                          "task_budget_s", "max_request_bytes", "input_budget_kind")
                configuration = {key: event.get(key) for key in fields}
                break
    model_method = method != "A-fixed"
    diagnosis = row.get("diagnosis") if isinstance(row.get("diagnosis"), dict) else {}
    value = diagnosis.get("initially_leaking")
    diagnosis_valid = type(value) is bool and nonempty(diagnosis.get("diagnosis"))
    unsafe = labels[case]["expected_initial"] == "UNSAFE"
    submissions, reproductions, feedback_events = [], [], []
    candidate_codes, original_hash = {}, None
    for action in actions:
        args, result = action["arguments"] or {}, action["result"] or {}
        if action["tool"] == "read_code" and isinstance(result, dict):
            original_hash = result.get("sha256", original_hash)
        if action["tool"] == "run_controlled_case" and isinstance(result, dict):
            observation = result.get("observation", {})
            reproduced = (args.get("candidate_id", "original") == "original"
                          and observation.get("verdict") == "FAIL"
                          and "CREDENTIAL_LEAK" in observation.get("reasons", []))
            item = {"trace_index": action["trace_index"], "originating_model_call": action["originating_model_call"],
                    "candidate_id": args.get("candidate_id", "original"), "hypothesis": args.get("hypothesis"),
                    "hypothesis_nonempty": nonempty(args.get("hypothesis")),
                    "hypothesis_quality": "MANUAL_REVIEW_REQUIRED", "request": args.get("request"),
                    "auth_mode": args.get("auth_mode"), "evidence_id": result.get("evidence_id"),
                    "verdict": observation.get("verdict"), "reasons": observation.get("reasons", []),
                    "leak_channels": observation.get("leak_channels", []), "original_leak_reproduced": reproduced}
            reproductions.append(item)
            if observation.get("verdict") == "FAIL":
                feedback_events.append((action, "controlled_failure"))
        if action["tool"] == "verify_patch" and isinstance(result, dict) and result.get("verdict") == "FAIL":
            feedback_events.append((action, "verification_failure"))
        if action["tool"] == "submit_patch" and isinstance(result, dict) and result.get("candidate_id"):
            candidate_id = result["candidate_id"]
            code = args.get("content")
            candidate_codes[candidate_id] = code
            submissions.append({"trace_index": action["trace_index"], "candidate_id": candidate_id,
                                "originating_model_call": action["originating_model_call"],
                                "rationale": args.get("rationale"), "source_sha256": result.get("source_sha256"),
                                "action": action})
    adaptations = []
    for submission in submissions:
        for feedback, kind in feedback_events:
            if feedback["trace_index"] >= submission["trace_index"]:
                continue
            previous_id = (feedback["arguments"] or {}).get("candidate_id", "original")
            previous_code = candidate_codes.get(previous_id)
            current_code = candidate_codes[submission["candidate_id"]]
            if previous_id == "original":
                changed = bool(original_hash and submission["source_sha256"] != original_hash)
            else:
                changed = isinstance(previous_code, str) and current_code != previous_code
            delivered = feedback_in_request(feedback, submission["action"], folder)
            feedback_result = feedback["result"].get("observation", {}) if kind == "controlled_failure" else feedback["result"]
            adaptations.append({"feedback_trace_index": feedback["trace_index"], "feedback_kind": kind,
                                "failed_candidate_id": previous_id, "next_candidate_id": submission["candidate_id"],
                                "proposal_trace_index": submission["trace_index"],
                                "feedback_in_later_model_request": delivered, "source_changed_from_failed_candidate": changed,
                                "credential_leak_feedback": "CREDENTIAL_LEAK" in feedback_result.get("reasons", []),
                                "is_revision_of_failed_patch": previous_id != "original",
                                "semantic_use_of_feedback": "MANUAL_REVIEW_REQUIRED" if delivered and changed else "NOT_ESTABLISHED"})
    final_id = submissions[-1]["candidate_id"] if submissions else "original"
    final_result = row.get("final_validation", {})
    final_pass = final_result.get("verdict") == "PASS"
    active_verifications = [a for a in actions if a["tool"] == "verify_patch"
                            and (a["arguments"] or {}).get("candidate_id") == final_id
                            and (a["result"] or {}).get("verdict") == "PASS"]
    first_patch = submissions[0]["trace_index"] if submissions else None
    reproduced_before_patch = [r for r in reproductions if r["original_leak_reproduced"]
                               and r["hypothesis_nonempty"] and first_patch is not None and r["trace_index"] < first_patch]
    # Completing a later model request containing observed original leakage is
    # necessary before attributing a proposal to runtime evidence.
    informed_original_patch = any(a["feedback_in_later_model_request"] and a["source_changed_from_failed_candidate"]
                                  and a["failed_candidate_id"] == "original" and a["credential_leak_feedback"]
                                  and a["feedback_kind"] == "controlled_failure" for a in adaptations)
    completed = bool(model and model.get("status") == "COMPLETED")
    read_source = any(a["tool"] == "read_code" and isinstance(a["result"], dict) and a["result"].get("source") for a in actions)
    if method != "C-agent":
        process_gate = None
        process_status = "NOT_APPLICABLE"
    else:
        if unsafe:
            process_gate = bool(completed and diagnosis_valid and value is True and read_source and
                                reproduced_before_patch and informed_original_patch and submissions and
                                row.get("source_changed") is True and active_verifications and final_pass)
        else:
            process_gate = bool(completed and diagnosis_valid and value is False and read_source and
                                final_id == "original" and active_verifications and final_pass)
        process_status = "MANUAL_REVIEW_REQUIRED" if process_gate else "NOT_ESTABLISHED"
    usage = (model or {}).get("usage", [])
    reported = [u.get("usage") for u in usage if isinstance(u.get("usage"), dict)]
    def tokens(name):
        values = [u.get(name) for u in reported]
        return sum(values) if values and all(type(v) is int for v in values) else None
    final_reasons = final_result.get("reasons", [])
    function_codes = {"RESPONSE_CONTRACT", "AUTH_CALL_COUNT", "AUTH_CREDENTIAL_MISMATCH",
                      "AUTH_RESOURCE_MISMATCH", "UNHANDLED_EXCEPTION", "NON_JSON_RETURN"}
    for submission in submissions:
        del submission["action"]
    return {"case": case, "method": method,
            "family": "D-no-feedback" if method.startswith("D-no-feedback-") else method,
            "registered_initial": "UNSAFE" if unsafe else "SAFE",
            "final_verdict": final_result.get("verdict", "UNKNOWN"), "final_reasons": final_reasons,
            "artifact_pass": final_pass, "model_status": (model or {}).get("status", "NOT_APPLICABLE"),
            "diagnosis_valid": diagnosis_valid if model_method else None,
            "diagnosis_correct": (value == unsafe) if diagnosis_valid and model_method else None,
            "diagnosis_text": diagnosis.get("diagnosis"),
            "safe_false_alarm": (value is True) if not unsafe and diagnosis_valid and model_method else None,
            "source_changed": row.get("source_changed") if method in {"A-fixed", "C-agent"} or row.get("candidate_count", 0) > 0 else None,
            "candidate_count": row.get("candidate_count", 0), "functional_failure": bool(function_codes & set(final_reasons)),
            "source_profile_failure": any(r.startswith("SOURCE_") for r in final_reasons),
            "original_leak_reproduction_count": sum(r["original_leak_reproduced"] for r in reproductions) if method == "C-agent" else None,
            "reproduction_before_first_patch": bool(reproduced_before_patch) if method == "C-agent" else None,
            "active_final_verification_pass": bool(active_verifications) if method == "C-agent" else None,
            "process_mechanical_gate": process_gate, "process_success": process_status,
            "failure_feedback_revision_observed": any(a["is_revision_of_failed_patch"] and a["feedback_in_later_model_request"]
                                                       and a["source_changed_from_failed_candidate"] for a in adaptations) if method == "C-agent" else None,
            "failed_patch_feedback_count": sum((a["arguments"] or {}).get("candidate_id", "original") != "original"
                                               for a, _ in feedback_events) if method == "C-agent" else None,
            "controlled_trials": reproductions, "proposals": submissions, "feedback_sequences": adaptations,
            "model_calls": (model or {}).get("model_calls", 0), "completion_tokens_reported": tokens("completion_tokens"),
            "recorded_client_configuration": configuration, "model_task_elapsed_s": (model or {}).get("elapsed_s"),
            "prompt_tokens_reported": tokens("prompt_tokens"), "usage_reports": len(reported),
            "model_calls_without_usage": (model or {}).get("model_calls", 0) - len(reported),
            "isolated_execution_count": row.get("isolated_execution_count"), "elapsed_s_including_final_validation": row.get("elapsed_s"),
            "record": (folder / "result.json").as_posix()}


def summarize(run):
    results_path = run / "results.json"
    data = read_json(results_path)
    manifest_path = Path(__file__).with_name("fixtures") / "manifest.json"
    manifest = read_json(manifest_path)
    frozen = read_json(run / "frozen-inputs.json")
    expected_hash = frozen.get("hashes", {}).get("agent_pilot/fixtures/manifest.json")
    if expected_hash != digest(manifest_path):
        raise ValueError("Manifest differs from the recorded freeze; do not infer labels")
    labels = {x["id"]: x for x in manifest["cases"]}
    rows = [score(entry, labels, run) for entry in data["rows"]]
    groups = defaultdict(list)
    for row in rows:
        groups[row["family"]].append(row)
    aggregates = {}
    for family, items in groups.items():
        unsafe = [r for r in items if r["registered_initial"] == "UNSAFE"]
        safe = [r for r in items if r["registered_initial"] == "SAFE"]
        ratio = lambda good, items: {"numerator": sum(good(r) for r in items), "denominator": len(items)}
        aggregates[family] = {"observed_case_attempts": len(items), "unique_cases": len({r["case"] for r in items}),
            "unit": "candidate attempts across two preselected cases" if family == "D-no-feedback" else "cases",
            "repair_artifact_pass": ratio(lambda r: r["artifact_pass"], unsafe),
            "safe_artifact_pass": ratio(lambda r: r["artifact_pass"], safe),
            "safe_source_changed": ratio(lambda r: r["source_changed"] is True, safe),
            "safe_false_alarm": ratio(lambda r: r["safe_false_alarm"] is True, safe) if family != "A-fixed" else None,
            "safe_diagnosis_unknown": sum(r["diagnosis_valid"] is False for r in safe) if family != "A-fixed" else None,
            "correct_diagnosis": ratio(lambda r: r["diagnosis_correct"] is True, items) if family != "A-fixed" else None,
            "diagnosis_unknown": sum(r["diagnosis_valid"] is False for r in items) if family != "A-fixed" else None,
            "final_unknown": sum(r["final_verdict"] == "UNKNOWN" for r in items),
            "functional_failure": sum(r["functional_failure"] for r in items),
            "source_profile_failure": sum(r["source_profile_failure"] for r in items),
            "process_mechanical_gate": ratio(lambda r: r["process_mechanical_gate"] is True, unsafe) if family == "C-agent" else None,
            "safe_process_mechanical_gate": ratio(lambda r: r["process_mechanical_gate"] is True, safe) if family == "C-agent" else None,
            "observed_revision_after_failed_patch": ratio(lambda r: r["failure_feedback_revision_observed"] is True,
                [r for r in items if r["failed_patch_feedback_count"]]) if family == "C-agent" else None,
            "manually_confirmed_process_success": "NOT_REVIEWED" if family == "C-agent" else "NOT_APPLICABLE",
            "missing_registered_cases": sorted(set(labels) - {r["case"] for r in items}) if family != "D-no-feedback" else [],
            "model_status_counts": dict(Counter(r["model_status"] for r in items))}
    return {"schema": "credproof.agent.process-summary.v1", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "records": run.as_posix(), "results_sha256": digest(results_path), "summarizer_sha256": digest(Path(__file__)),
            "registered_manifest_sha256": digest(manifest_path), "frozen_inputs_unchanged_reported": data.get("frozen_inputs_unchanged"),
            "interpretation": "Read-only derivation. Mechanical event gates are not semantic hypothesis-quality or causal-feedback judgments. No absent model arm is scored.",
            "aggregates": aggregates, "rows": rows}


def write_outputs(summary, destination):
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    fields = ["case", "method", "registered_initial", "final_verdict", "model_status", "diagnosis_valid", "diagnosis_correct",
              "safe_false_alarm", "source_changed", "original_leak_reproduction_count", "reproduction_before_first_patch",
              "active_final_verification_pass", "process_mechanical_gate", "process_success", "failure_feedback_revision_observed",
              "model_calls", "completion_tokens_reported", "isolated_execution_count", "elapsed_s_including_final_validation"]
    with (destination / "cases.csv").open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(summary["rows"])
    lines = ["# Recorded outcomes and process evidence", "", "Final artifact PASS and observed Agent process are separate. Hypothesis quality and feedback rationale require human review. Missing methods have no reported score.", "",
             "| Case | Method | Final artifact | Model status | Original leak reproduced | Process evidence |",
             "|---|---|---|---|---|---|"]
    for row in summary["rows"]:
        reproduction = row["original_leak_reproduction_count"]
        lines.append(f"| {row['case']} | {row['method']} | {row['final_verdict']} | {row['model_status']} | {reproduction if reproduction is not None else 'N/A'} | {row['process_success']} |")
    lines.extend(["", "The JSON contains quoted hypotheses, model-selected inputs, proposal rationales, trace positions, and whether feedback actually appeared in a later model request. A same-response parallel tool call is not feedback use.", "",
                  "C versus D shares a configured maximum generated-token ceiling only. Actual tokens, context, model calls, wall time and execution feedback differ. D covers two predetermined cases, with three attempts each; it is not six independent cases.", ""])
    (destination / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run, destination = args.records.resolve(), args.output.resolve()
    if destination == run or run in destination.parents or destination.exists():
        raise SystemExit("Output must be a new directory outside the existing records")
    summary = summarize(run)
    write_outputs(summary, destination)
    print(json.dumps({"output": str(destination), "rows": len(summary["rows"]),
                      "families": list(summary["aggregates"]), "candidate_executed": False}, ensure_ascii=False))


if __name__ == "__main__":
    main()
