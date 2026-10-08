"""Qwen-Agent Assistant with a local-only, audited Ollama transport.

The official Assistant/FnCallAgent loop remains in use. We override its optional
knowledge path and TextChatAtOAI._chat_stream only; the latter yields one complete
native-tool-call result, preserving raw responses and real usage when available.
This client does not execute arbitrary commands or determine repair correctness.
"""
from __future__ import annotations

import copy
import hashlib
import json
import queue
import threading
import time
import urllib.request
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Sequence

from qwen_agent.agents import Assistant
from qwen_agent.llm.oai import TextChatAtOAI
from qwen_agent.llm.schema import Message
from qwen_agent.tools.base import BaseTool

BASE_URL = "http://127.0.0.1:11435/v1"
MODEL = "qwen3-coder:30b"
MAX_REQUEST_BYTES = 262_144
MAX_RESPONSE_BYTES = 2_097_152
CONTEXT_TOKENS = 16_384
TEMPLATE_RESERVE = 512
NEW_MESSAGE_RESERVE = 512
FORMAT_CORRECTION = (
    "The trusted executor still has outstanding required checks. Your previous "
    "turn ended with a text reply without completing them. If you can continue, "
    "make an actual tool call following the tool-calling format supplied with "
    "the tool definitions, rather than explaining or quoting an example call. "
    "If a proposed call appeared only as plain text, that text did not execute a tool. "
    "Do not invent results or change task requirements. If you cannot continue, "
    "state the limitation; the task will remain incomplete. This is the only "
    "format correction request and it uses the original task budget."
)


class BudgetExceeded(RuntimeError):
    """No more actions may be dispatched by this task."""


class InputBudgetViolation(RuntimeError):
    """A server observation contradicted the recorded conservative budget."""


class _ExecutorCompleted(Exception):
    """Internal control flow: an audited tool completed the trusted executor."""


class _ExecutionCompletionError(RuntimeError):
    """The trusted completion callback failed or returned invalid data."""


def _json_structure(value: Any) -> str:
    """Compare JSON structure, including primitive types, without key ordering."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _valid_prompt_count(value: Any) -> bool:
    # bool is an int subclass; zero placeholders must not become measurements.
    return type(value) is int and 0 < value <= CONTEXT_TOKENS


def estimate_input_budget(payload: dict, max_output_tokens: int, previous: dict | None = None) -> dict:
    """Pure budget arithmetic; previous must come from this client's last response.

    The first request/fallback counts complete wire bytes. With an exact prior
    structural prefix, use its observed prompt tokens plus complete suffix JSON
    bytes and 512 framing tokens per new message. This is a conservative pilot
    estimate for the frozen model/template, not a tokenizer correctness proof.
    """
    wire_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    bound = wire_bytes
    method = "UTF8_WIRE_BYTES"
    reason = "no_previous_measured_request"
    prefix_call_id = prefix_tokens = suffix_bytes = new_count = None
    if previous is not None:
        prior = previous.get("payload")
        measured = previous.get("prompt_tokens")
        prior_messages = prior.get("messages") if isinstance(prior, dict) else None
        messages = payload.get("messages")
        if not _valid_prompt_count(measured):
            reason = "invalid_previous_prompt_tokens"
        elif (not isinstance(prior_messages, list) or not prior_messages
              or not isinstance(messages, list)
              or not all(isinstance(item, dict) for item in [*prior_messages, *messages])):
            reason = "unsupported_message_structure"
        elif _json_structure({k: v for k, v in prior.items() if k != "messages"}) != _json_structure(
                {k: v for k, v in payload.items() if k != "messages"}):
            reason = "request_configuration_changed"
        elif (len(messages) < len(prior_messages)
              or _json_structure(messages[:len(prior_messages)]) != _json_structure(prior_messages)):
            reason = "message_prefix_changed"
        else:
            suffix = messages[len(prior_messages):]
            suffix_bytes = len(json.dumps(suffix, ensure_ascii=False).encode("utf-8"))
            new_count = len(suffix)
            prefix_tokens = measured
            prefix_call_id = previous.get("call_id")
            bound = measured + suffix_bytes + NEW_MESSAGE_RESERVE * new_count
            method = "MEASURED_PREFIX_PLUS_UTF8_SUFFIX"
            reason = "exact_previous_request_prefix_and_configuration"
    input_limit = CONTEXT_TOKENS - max_output_tokens - TEMPLATE_RESERVE
    return {
        "method": method, "reuse_reason": reason, "request_bytes": wire_bytes,
        "prefix_call_id": prefix_call_id, "prefix_prompt_tokens": prefix_tokens,
        "suffix_json_bytes": suffix_bytes, "new_message_count": new_count,
        "new_message_reserve_tokens": NEW_MESSAGE_RESERVE * (new_count or 0),
        "global_reserve_tokens": TEMPLATE_RESERVE, "max_output_tokens": max_output_tokens,
        "input_token_upper_bound": bound, "input_token_limit": input_limit,
        "context_token_upper_bound": bound + max_output_tokens + TEMPLATE_RESERVE,
        "context_token_limit": CONTEXT_TOKENS,
        "within_context_budget": bound <= input_limit,
        "within_wire_limit": wire_bytes <= MAX_REQUEST_BYTES,
    }


def check_reported_prompt_tokens(budget: dict, usage: dict | None) -> int | None:
    """Validate an observation before making any returned tool call actionable."""
    count = usage.get("prompt_tokens") if isinstance(usage, dict) else None
    if type(count) is int and count > 0:
        if count > budget["input_token_upper_bound"] or count > budget["input_token_limit"]:
            raise InputBudgetViolation("Server prompt_tokens exceeded the recorded input bound; response discarded")
        return count
    return None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_ollama_messages(messages: Sequence[Message | dict]) -> list[dict]:
    """Convert Qwen messages without upstream's tool-result `id` mismatch.

    Qwen-Agent 0.0.34 BaseChatModel._conv_qwen_agent_messages_to_oai puts a
    tool-result identifier in `id`; the OpenAI chat wire contract instead uses
    `tool_call_id`. Do not send internal `extra`, `function_call`, or name fields.
    Only plain text is accepted; file/image/RAG paths are intentionally absent.
    """
    result: list[dict] = []
    for item in messages:
        msg = item.model_dump() if isinstance(item, Message) else copy.deepcopy(item)
        role = msg.get("role")
        content = msg.get("content") or ""
        if isinstance(content, list):
            if any(set(part) - {"text"} for part in content):
                raise ValueError("Only plain-text messages are permitted")
            content = "".join(part.get("text", "") for part in content)
        if not isinstance(content, str):
            raise ValueError("Message content must be text")
        if role in {"system", "user"}:
            result.append({"role": role, "content": content})
        elif role == "assistant":
            # Qwen represents each tool call as its own Message. Recombine only
            # immediately adjacent assistant records, retaining IDs and arguments.
            if not result or result[-1]["role"] != "assistant":
                result.append({"role": "assistant", "content": ""})
            target = result[-1]
            target["content"] += content
            if msg.get("reasoning_content"):
                target["reasoning_content"] = target.get("reasoning_content", "") + msg["reasoning_content"]
            if msg.get("function_call"):
                call = msg["function_call"]
                call_id = msg.get("extra", {}).get("function_id")
                if not isinstance(call_id, str) or not call_id:
                    raise ValueError("Tool call is missing its server-provided ID")
                target.setdefault("tool_calls", []).append({
                    "id": call_id, "type": "function", "function": call,
                })
        elif role == "function":
            call_id = msg.get("extra", {}).get("function_id")
            if not isinstance(call_id, str) or not call_id:
                raise ValueError("Tool result is missing its matching call ID")
            result.append({"role": "tool", "tool_call_id": call_id, "content": content})
        else:
            raise ValueError(f"Unsupported Qwen message role: {role!r}")
    return result


def compact_messages_for_budget(messages: Sequence[Message | dict]) -> list[dict]:
    """Compact a repair conversation without changing executor evidence.

    The old implementation cut the history at the last ``submit``/``verify``
    call and rewrote every retained evidence result as ``OK``.  That could
    remove the submitted source and turn a real rejection into a success.  We
    now select *paired* call/result records: the latest accepted candidate,
    its latest verification, the latest successful evidence/source reads, and
    every non-OK result.  The retained function content is never rewritten;
    full raw history remains in the host artifact.  In particular, a source
    read performed after an accepted candidate is still current evidence: it
    is not dropped merely because the path is not under ``tests/``.
    """
    copied = [item.model_dump() if isinstance(item, Message) else copy.deepcopy(item)
              for item in messages]
    if len(copied) <= 2:
        return copied

    def _ident(item: dict) -> str | None:
        extra = item.get('extra')
        value = extra.get('function_id') if isinstance(extra, dict) else None
        return value if isinstance(value, str) and value else None

    def _json_result(item: dict) -> dict:
        if item.get('role') != 'function' or not isinstance(item.get('content'), str):
            return {}
        try:
            value = json.loads(item['content'])
        except (TypeError, ValueError):
            return {}
        return value if isinstance(value, dict) else {}

    def _source_digest(code: object) -> str | None:
        if not isinstance(code, str):
            return None
        return hashlib.sha256(code.replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')).hexdigest()

    def _compact_feedback(value: dict) -> dict:
        """Keep trusted decision fields while dropping repeated raw observations."""
        result = {key: value[key] for key in (
            'schema', 'object_id', 'verdict', 'reason', 'required_checks',
            'confirmed_failed_checks', 'readable_paths', 'repair_guidance',
            'credential_leaks', 'pytest_summary', 'forbidden_reads', 'violation_facts',
            'actionable_failures', 'out_of_scope_reads', 'unauthorized_connections', 'executor_state',
        ) if key in value}
        scenarios = value.get('scenario_summary')
        if isinstance(scenarios, list):
            result['scenario_summary'] = [{key: row[key] for key in (
                'name', 'expected_error', 'require_network', 'observed',
                'raised_type', 'returned_fields', 'service_observation_count',
                'service_paths') if key in row} for row in scenarios[:8] if isinstance(row, dict)]
        requests = value.get('request_summary')
        if isinstance(requests, list):
            result['request_summary'] = requests[:4]
            result['request_summary_omitted'] = max(
                value.get('request_summary_omitted', 0), len(requests) - 4)
        access = value.get('access_summary')
        if isinstance(access, dict):
            result['access_summary'] = {key: access[key] for key in (
                'credential_success_evidence', 'observed_credential_outputs',
                'forbidden_read_count', 'out_of_scope_read_count',
                'unauthorized_connection_count') if key in access}
        return result

    def _compact_failure(value: dict) -> dict:
        """Keep actionable failure evidence without repeating every row."""
        return {key: value[key] for key in (
            'schema', 'object_id', 'verdict', 'reason', 'required_checks',
            'confirmed_failed_checks', 'credential_leaks', 'pytest_summary', 'violation_facts',
            'actionable_failures', 'forbidden_reads', 'out_of_scope_reads', 'unauthorized_connections')
            if key in value}

    def _compact_function_content(item: dict, name: str, value: dict) -> dict:
        # Keep the decision-bearing fields of a non-OK result.  The complete
        # response remains in the host audit log; the model turn needs the
        # exact status/reason, object identifiers and latest executor state,
        # not repeated raw diagnostics that can consume the next budget.
        if value.get('status') not in {'OK', 'ACCEPTED_FOR_VERIFICATION'}:
            return {key: value[key] for key in (
                'status', 'reason', 'error', 'message', 'tool',
                'candidate', 'candidate_sha256', 'path', 'read_sha256',
                'missing_paths', 'repeated_read_count', 'tool_call_count',
                'verification', 'executor_state') if key in value}
        result = copy.deepcopy(value)
        if name == 'get_evidence':
            result = {'status': 'OK', **_compact_feedback(value)}
        elif name == 'verify_patch':
            nested = result.get('report')
            if isinstance(nested, dict):
                result['report'] = _compact_feedback(nested)
            else:
                result = {key: result[key] for key in ('status', 'candidate', 'verification', 'executor_state')
                          if key in result}
        elif name == 'submit_patch' and result.get('status') == 'ACCEPTED_FOR_VERIFICATION':
            nested = result.get('verification')
            if isinstance(nested, dict) and isinstance(nested.get('report'), dict):
                nested = copy.deepcopy(nested)
                nested['report'] = _compact_failure(nested['report'])
                result['verification'] = nested
        return result

    calls: dict[str, tuple[int, str, dict]] = {}
    results: dict[str, tuple[int, dict]] = {}
    for index, item in enumerate(copied):
        if not isinstance(item, dict):
            continue
        ident = _ident(item)
        if not ident:
            continue
        if item.get('role') == 'assistant' and isinstance(item.get('function_call'), dict):
            name = item['function_call'].get('name')
            if isinstance(name, str):
                calls[ident] = (index, name, item)
        elif item.get('role') == 'function':
            results[ident] = (index, _json_result(item))

    pairs: list[tuple[int, int, str, dict, dict]] = []
    for ident, (call_index, name, call_item) in calls.items():
        result = results.get(ident)
        if result is not None:
            result_index, result_value = result
            pairs.append((call_index, result_index, ident, call_item, result_value))
    if not any(name in {'submit_patch', 'verify_patch'} for _, _, _, call, _ in pairs
               for name in [call.get('function_call', {}).get('name')]):
        return copied

    selected: set[str] = set()
    # Non-OK decisions remain evidence. An earlier accepted candidate is
    # superseded by the latest accepted candidate, not an error to repeat.
    for _, _, ident, _, value in pairs:
        if value.get('status') not in (None, 'OK', 'ACCEPTED_FOR_VERIFICATION'):
            selected.add(ident)

    def latest_matching(predicate):
        candidates = [pair for pair in pairs if predicate(pair[3].get('function_call', {}).get('name'), pair[4])]
        return max(candidates, key=lambda pair: pair[1]) if candidates else None

    accepted = latest_matching(lambda name, value: name == 'submit_patch' and
                               value.get('status') == 'ACCEPTED_FOR_VERIFICATION')
    if accepted:
        selected.add(accepted[2])
    latest_verify = latest_matching(lambda name, value: name == 'verify_patch')
    if latest_verify:
        selected.add(latest_verify[2])
    # Keep the latest successful evidence and one successful read for every
    # path.  These are the minimum trusted rules/source context for the next
    # modification request.  The submitted candidate body remains in the
    # accepted submit call's arguments, never as a hash-only placeholder.
    latest_evidence = latest_matching(lambda name, value: name == 'get_evidence' and value.get('status') == 'OK')
    if latest_evidence and (not latest_verify or latest_verify[4].get('status') != 'OK'):
        selected.add(latest_evidence[2])
    read_candidates = {}
    for pair in pairs:
        name = pair[3].get('function_call', {}).get('name')
        if name != 'read_code' or pair[4].get('status') != 'OK':
            continue
        try:
            args = json.loads(pair[3]['function_call'].get('arguments') or '{}')
        except (TypeError, ValueError):
            args = {}
        path = args.get('path') if isinstance(args, dict) else None
        # Keep the newest successful read for *every* path.  The previous
        # ``accepted`` shortcut kept only tests after a candidate was
        # accepted, which made repeated tool.py reads disappear from the next
        # model request even though the host had just executed them.
        if isinstance(path, str):
            read_candidates[path] = pair

    # A source read that happened before the accepted submit is stale for the
    # mutable entry.  Keep declared tests (they are not changed by submit),
    # but let the accepted submit pair carry the current entry source when no
    # post-submit read exists.  This avoids presenting the pre-patch body as
    # the current candidate while still preserving every newest post-action
    # read pair.
    if accepted:
        for path, pair in list(read_candidates.items()):
            if pair[1] <= accepted[0] and not ('/tests/' in path or path.startswith('tests/')):
                read_candidates.pop(path, None)
    selected.update(pair[2] for pair in read_candidates.values())

    # If the newest full read is the accepted candidate's current source, the
    # old submit call's source argument is a duplicate.  Remove that *old
    # paired event* instead of truncating the current read or inventing a
    # placeholder tool result.  The trusted context block below carries the
    # candidate id/hash and the exact auto-verification feedback.
    accepted_summary = None
    if accepted:
        accepted_value = accepted[4]
        verification = accepted_value.get('verification')
        report = verification.get('report') if isinstance(verification, dict) else None
        failure_summary = None
        if isinstance(report, dict):
            # The full verification remains on disk.  The next model turn
            # needs the decision inputs and failed checks, not repeated
            # scenario/request rows already present in the host artifact.
            failure_summary = {key: report[key] for key in (
                'schema', 'object_id', 'verdict', 'reason', 'required_checks',
                'confirmed_failed_checks', 'credential_leaks', 'pytest_summary', 'violation_facts',
                'actionable_failures', 'forbidden_reads', 'out_of_scope_reads', 'unauthorized_connections')
                if key in report}
        accepted_summary = {
            'candidate': accepted_value.get('candidate'),
            'candidate_sha256': accepted_value.get('candidate_sha256'),
            'verification_action': accepted_value.get('verification_action'),
            'verification_count': accepted_value.get('verification_count'),
            'verification': {
                key: value for key, value in (
                    ('status', verification.get('status')),
                    ('candidate', verification.get('candidate')),
                    ('verification', verification.get('verification')),
                    ('report', failure_summary),
                ) if value is not None
            } if isinstance(verification, dict) else None,
        }

        candidate_sha = accepted_value.get('candidate_sha256')
        current_read_is_candidate = any(
            _source_digest(pair[4].get('code')) == candidate_sha
            for pair in read_candidates.values()
        )
        if isinstance(candidate_sha, str) and current_read_is_candidate:
            selected.discard(accepted[2])
            # The accepted response already contains the program-owned
            # verification report.  Once the current candidate source is
            # present, repeating get_evidence would only duplicate the same
            # rules/checks and consume the next request's budget.
            if latest_evidence and isinstance(report, dict):
                selected.discard(latest_evidence[2])
    # The accepted program-auto-verification report is the newest evidence.
    # Keep the initial task contract and that failure, but do not repeat the
    # earlier get_evidence payload while the candidate source is carried by
    # either the submit call or a newer full read.
    if (accepted and latest_evidence and isinstance(accepted[4].get('verification'), dict)
            and isinstance(accepted[4]['verification'].get('report'), dict)):
        selected.discard(latest_evidence[2])

    # A model response may contain more than one native call.  Retain the
    # complete newest adjacent assistant-call batch and all of its matching
    # results.  This prevents an orphan call/result when older history is
    # removed and makes the latest host action observable on the next turn.
    assistant_batches: list[list[str]] = []
    current_batch: list[str] = []
    for item in copied[2:]:
        ident = _ident(item)
        is_call = (item.get('role') == 'assistant' and
                   isinstance(item.get('function_call'), dict) and ident in calls)
        if is_call:
            if not current_batch:
                current_batch = []
                assistant_batches.append(current_batch)
            current_batch.append(ident)
        else:
            current_batch = []
    if assistant_batches:
        selected.update(ident for ident in assistant_batches[-1]
                        if ident in results)

    # Reassemble whole assistant/function pairs in their original order.  The
    # base system/user task remains the first two messages.  Unpaired messages
    # are dropped rather than inventing a tool result or changing a status.
    keep_indices = {index for pair in pairs if pair[2] in selected for index in pair[:2]}
    compacted = copied[:2]
    latest_host_state = next((copy.deepcopy(pair[4]['executor_state'])
                              for pair in sorted(pairs, key=lambda p: p[1], reverse=True)
                              if isinstance(pair[4].get('executor_state'), dict)), None)
    # NO_CHANGE contains the current source once more. Keep the newest full
    # call/result pair and map a duplicate read body to that visible argument.
    # No source is removed unless its complete same-object text is retained.
    duplicate_source_call = latest_matching(
        lambda name, value: name == 'submit_patch'
        and value.get('status') == 'REJECTED'
        and value.get('reason') == 'NO_CHANGE')
    if duplicate_source_call is not None and duplicate_source_call[2] not in selected:
        duplicate_source_call = None
    if duplicate_source_call is not None:
        try:
            args = json.loads(duplicate_source_call[3]['function_call'].get('arguments') or '{}')
            code = args.get('code') if isinstance(args, dict) else None
            if (isinstance(code, str) and _source_digest(code) == duplicate_source_call[4].get('candidate_sha256')
                    and latest_host_state is not None
                    and duplicate_source_call[4].get('candidate_sha256') == latest_host_state.get('current_candidate_sha256')):
                pass
            else:
                duplicate_source_call = None
        except (TypeError, ValueError):
            duplicate_source_call = None
    source_deduplication = []
    selected_names = {ident: calls[ident][1] for ident in selected}
    for index, item in enumerate(copied[2:], start=2):
        if index not in keep_indices:
            continue
        ident = _ident(item)
        if item.get('role') == 'function' and ident in selected_names:
            original = _json_result(item)
            name = selected_names[ident]
            if (original.get('status') not in (None, 'OK', 'ACCEPTED_FOR_VERIFICATION')):
                item = copy.deepcopy(item)
                item['content'] = json.dumps(_compact_function_content(item, name, original),
                                             ensure_ascii=False, separators=(',', ':'))
            elif ((original.get('status') == 'OK' and name in {'get_evidence', 'verify_patch'}) or
                    (original.get('status') == 'ACCEPTED_FOR_VERIFICATION' and name == 'submit_patch')):
                item = copy.deepcopy(item)
                item['content'] = json.dumps(_compact_function_content(item, name, original),
                                             ensure_ascii=False, separators=(',', ':'))
            # The authoritative latest state is carried once in a separate
            # executor-context block. Old per-tool counters must not compete
            # with it. Preserve the paired status/source and label the mapping.
            value = _json_result(item)
            if (duplicate_source_call is not None and name == 'read_code'
                    and value.get('status') == 'OK'
                    and _source_digest(value.get('code')) == duplicate_source_call[4].get('candidate_sha256')):
                value.pop('code')
                value['code_relation'] = {
                    'source_call_id': duplicate_source_call[2],
                    'source_field': 'function.arguments.code',
                    'code_sha256': duplicate_source_call[4]['candidate_sha256'],
                    'same_current_object': True,
                }
                source_deduplication.append({'read_call_id': ident, **value['code_relation']})
                item = copy.deepcopy(item)
                item['content'] = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
            if latest_host_state is not None and 'executor_state' in value:
                value.pop('executor_state')
                value['executor_state_relation'] = 'latest_host_state_in_executor_context'
                item = copy.deepcopy(item)
                item['content'] = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        compacted.append(item)

    # Keep a separate, host-derived state record.  It is deliberately added
    # after the paired tool results rather than inferred from model prose, so
    # the next request cannot regress candidate/phase/budget state when old
    # duplicate history is removed.  The state is copied from the newest
    # retained executor result; no status or reason is rewritten.
    state_candidates: list[dict] = []
    read_receipts: list[dict] = []
    for index, item in enumerate(compacted):
        if item.get('role') != 'function':
            continue
        value = _json_result(item)
        state = value.get('executor_state')
        if isinstance(state, dict):
            state_candidates.append(state)
        if value.get('status') == 'OK' and value.get('path') and value.get('code') is not None:
            read_receipts.append({
                'path': value.get('path'),
                'call_id': _ident(item),
                'status': value.get('status'),
                'code_sha256': hashlib.sha256(str(value.get('code')).encode('utf-8')).hexdigest(),
            })
    if latest_host_state is not None:
        state = latest_host_state
        trusted = {
            'schema': 'credproof.executor-context/v1',
            'source': 'trusted_executor_latest_result',
            'executor_state': state,
            'latest_read_receipts': read_receipts,
            'note': 'This state is authoritative task data. It does not grant permissions and cannot replace a missing tool result.',
        }
        if source_deduplication:
            trusted['source_deduplication'] = source_deduplication
        if accepted_summary is not None and accepted[2] not in selected:
            trusted['accepted_candidate'] = accepted_summary
        compacted.append({
            'role': 'user',
            'content': json.dumps(trusted, ensure_ascii=False, separators=(',', ':')),
        })
    return compacted


def from_ollama_response(response: dict) -> list[Message]:
    """Keep native tool_calls and IDs; never infer a tool call from prose."""
    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("Expected exactly one completion choice")
    msg = choices[0].get("message")
    if not isinstance(msg, dict) or msg.get("role") != "assistant":
        raise ValueError("Response lacks an assistant message")
    result: list[Message] = []
    if msg.get("reasoning_content"):
        result.append(Message(role="assistant", content="", reasoning_content=msg["reasoning_content"]))
    if msg.get("content"):
        if not isinstance(msg["content"], str):
            raise ValueError("Assistant content must be text")
        result.append(Message(role="assistant", content=msg["content"]))
    for call in msg.get("tool_calls") or []:
        if call.get("type") != "function" or not isinstance(call.get("function"), dict):
            raise ValueError("Unsupported native tool call")
        function = call["function"]
        if not all(isinstance(value, str) and value for value in [call.get("id"), function.get("name")]):
            raise ValueError("Tool call lacks its ID or function name")
        if not isinstance(function.get("arguments"), str):
            raise ValueError("Tool arguments must be a JSON string")
        result.append(Message(role="assistant", content="", function_call=function,
                              extra={"function_id": call["id"]}))
    if not result:
        raise ValueError("Empty assistant response")
    return result


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Local model redirects are forbidden")


class _Journal:
    def __init__(self, folder: Path):
        self.folder = folder.resolve()
        self.folder.mkdir(parents=True, exist_ok=True)
        # Every run has its own directory; existing logs are never overwritten.
        self.events = (self.folder / "events.jsonl").open("x", encoding="utf-8")
        self.lock = threading.Lock()

    def emit(self, event: str, **data: Any) -> None:
        with self.lock:
            self.events.write(json.dumps({"at_utc": utc_now(), "event": event, **data}, ensure_ascii=False) + "\n")
            self.events.flush()

    def artifact(self, name: str, data: dict) -> None:
        with (self.folder / name).open("x", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")


class _LocalModel(TextChatAtOAI):
    def __init__(self, owner: "LocalAgentClient"):
        super().__init__({
            "model": MODEL, "model_type": "oai", "model_server": BASE_URL,
            "api_key": "ollama-local-placeholder",
            "generate_cfg": {"use_raw_api": True, "max_retries": 0,
                             "max_input_tokens": 0, "temperature": 0.2,
                             "top_p": 0.8, "max_tokens": owner.max_output_tokens, "seed": owner.seed},
        })
        self.owner = owner

    def _chat_stream(self, messages, delta_stream, generate_cfg):
        # Official raw_chat supplies `tools`; avoid the upstream nonstream path,
        # which does not preserve tool_calls in 0.0.34. There is no text parser.
        if delta_stream:
            raise ValueError("Delta streaming is not enabled for this pilot")
        permitted = {"temperature", "top_p", "max_tokens", "seed", "tools"}
        if set(generate_cfg) - permitted:
            raise ValueError(f"Unsupported generation fields: {sorted(set(generate_cfg) - permitted)}")
        compacted_messages = compact_messages_for_budget(messages)
        if len(compacted_messages) != len(messages):
            self.owner._journal.emit(
                "conversation_compacted",
                original_message_count=len(messages),
                retained_message_count=len(compacted_messages),
                retained_roles=[item.get("role") for item in compacted_messages],
                reason="candidate_phase_replaced_superseded_tool_history",
            )
        payload = {"model": MODEL, "messages": to_ollama_messages(compacted_messages),
                   "stream": False, **generate_cfg}
        raw = self.owner._request(payload)
        decoded = from_ollama_response(raw)
        self.owner._journal.emit(
            "native_response_decoded", call_id=self.owner.model_calls,
            native_tool_calls=sum(bool(item.function_call) for item in decoded),
            finish_reason=raw["choices"][0].get("finish_reason"),
            protocol="openai-compatible-native-tools", prose_execution_enabled=False)
        yield decoded


class _RestrictedAssistant(Assistant):
    def __init__(self, owner: "LocalAgentClient", **kwargs):
        self.owner = owner
        # FnCallAgent.__init__ checks this attribute before constructing Memory.
        self.mem = SimpleNamespace(system_files=[])
        super().__init__(files=None, **kwargs)

    def _prepend_knowledge_prompt(self, messages, **kwargs):
        # Explicitly disable Assistant's optional Memory/RAG/file retrieval path.
        return messages

    def _call_tool(self, tool_name, tool_args="{}", **kwargs):
        self.owner._check_budget()
        started = time.monotonic()
        self.owner._journal.emit("tool_request", name=tool_name, arguments=tool_args)
        if tool_name not in self.function_map:
            result = json.dumps({"error": "tool_not_allowed", "name": tool_name})
        else:
            # Detailed field/path/candidate checks and the 3-patch cap belong to
            # the upper-layer BaseTool implementation, before any side effects.
            result = super()._call_tool(tool_name, tool_args, **kwargs)
        self.owner._journal.emit("tool_result", name=tool_name, result=result,
                                 elapsed_s=time.monotonic() - started)
        if tool_name in self.function_map:
            # Outside super()._call_tool's exception handler: completion/error
            # must unwind FnCallAgent, including the rest of a parallel batch.
            self.owner._after_tool_result()
        self.owner._check_budget()
        return result


class LocalAgentClient:
    """One client = one task. Use only caller-created, bounded BaseTool objects.

    Network timeout stops the client and refuses further calls. It does not prove
    server generation stopped. The supervisor must enforce the process deadline
    and reset/confirm idle Ollama before starting a new task after a timeout.

    execution_completion is a trusted, zero-argument callback after each real
    registered tool result is audited. Return None to continue, or a nonempty
    JSON-serializable dict to end with EXECUTOR_COMPLETED and executor_result.
    This does not synthesize a model final response. The terminal tool result
    stays in the audit even when Qwen has not yet yielded it into messages.

    max_format_corrections=1 permits one explicit continuation after an ordinary
    text ending while the executor is incomplete. It uses this same task/call
    budget and full history; text is never parsed as an executable call. The
    default is zero, so one-shot controls and ordinary chat retain their policy.
    """
    def __init__(self, *, tools: Sequence[BaseTool], system_message: str,
                 log_dir: Path, max_model_calls: int = 12,
                 request_timeout_s: float = 120, task_budget_s: float = 900,
                 max_output_tokens: int = 2048, seed: int = 0,
                 execution_completion: Callable[[], dict | None] | None = None,
                 max_format_corrections: int = 0):
        if not 1 <= max_model_calls <= 12 or not 0 < request_timeout_s <= 120 or not 0 < task_budget_s <= 900:
            raise ValueError("Budgets may be reduced but not exceed 12 / 120 s / 900 s")
        if any(not isinstance(tool, BaseTool) for tool in tools):
            raise TypeError("Only explicit BaseTool instances are accepted")
        if not isinstance(max_output_tokens, int) or not 1 <= max_output_tokens <= 8192:
            raise ValueError("max_output_tokens must be an integer between 1 and 8192")
        if type(seed) is not int or not 0 <= seed <= 2**31 - 1:
            raise ValueError("seed must be an integer between 0 and 2**31 - 1")
        if len({tool.name for tool in tools}) != len(tools):
            raise ValueError("Duplicate tool names are forbidden")
        if any(tool.file_access for tool in tools):
            raise ValueError("Automatic file-access tools are forbidden")
        if execution_completion is not None and not callable(execution_completion):
            raise TypeError("execution_completion must be callable or None")
        if type(max_format_corrections) is not int or max_format_corrections not in (0, 1):
            raise ValueError("At most one explicit format correction is permitted")
        if max_format_corrections and (not tools or execution_completion is None):
            raise ValueError("Format correction requires tools and a trusted completion callback")
        self.max_model_calls = max_model_calls
        self.request_timeout_s = request_timeout_s
        self.task_budget_s = task_budget_s
        self.max_output_tokens = max_output_tokens
        self.seed = seed
        # Retain the first/fallback byte gate. Later requests may bind to only the
        # immediately preceding successful observation, never another task/run.
        self.max_request_bytes = min(MAX_REQUEST_BYTES, CONTEXT_TOKENS - max_output_tokens - TEMPLATE_RESERVE)
        self._last_measured_request: dict | None = None
        self.model_calls = 0
        self.usage: list[dict] = []
        self._started: float | None = None
        self._poisoned = False
        self._execution_completion = execution_completion
        self._executor_result: dict | None = None
        self.max_format_corrections = max_format_corrections
        self.format_correction_attempts = 0
        self.format_correction_call_ids: list[int] = []
        self._format_correction_pending = False
        self._journal = _Journal(Path(log_dir))
        self._assistant = _RestrictedAssistant(self, llm=_LocalModel(self),
                                               function_list=list(tools), system_message=system_message)
        self._journal.emit("client_created", framework="qwen-agent", framework_version=version("qwen-agent"),
                           model=MODEL, base_url=BASE_URL, tools=[tool.function for tool in tools],
                           max_model_calls=max_model_calls, request_timeout_s=request_timeout_s,
                           task_budget_s=task_budget_s, max_output_tokens=max_output_tokens, seed=seed,
                           initial_max_request_bytes=self.max_request_bytes,
                           absolute_max_request_bytes=MAX_REQUEST_BYTES,
                           input_budget_kind="EXACT_MEASURED_PREFIX_OR_UTF8_WIRE_BYTES",
                           context_tokens=CONTEXT_TOKENS, global_reserve_tokens=TEMPLATE_RESERVE,
                           per_new_message_reserve_tokens=NEW_MESSAGE_RESERVE,
                           execution_completion_enabled=execution_completion is not None,
                           max_format_corrections=max_format_corrections,
                           automatic_retries=0, knowledge_files_enabled=False)

    def _after_tool_result(self) -> None:
        if self._execution_completion is None:
            return
        try:
            terminal = self._execution_completion()
            if terminal is not None:
                if not isinstance(terminal, dict) or not terminal:
                    raise ValueError("Completion callback must return None or a nonempty terminal dict")
                # Freeze a JSON value rather than retaining mutable executor
                # state; non-JSON objects and NaN are callback errors.
                terminal = json.loads(json.dumps(terminal, ensure_ascii=False, allow_nan=False))
        except Exception as exc:
            self._journal.emit("execution_completion_error", error_type=type(exc).__name__, error=str(exc))
            # Even BudgetExceeded raised inside the callback is a callback
            # error, not a successful completion or an ordinary model limit.
            raise _ExecutionCompletionError(f"{type(exc).__name__}: {exc}") from exc
        self._journal.emit("execution_completion_checked", terminal=terminal is not None)
        if terminal is not None:
            self._journal.emit("executor_completed", executor_result=terminal)
            self._executor_result = terminal
            # Completion has precedence over a post-tool budget check: the last
            # allowed dispatch may itself produce the authoritative terminal.
            raise _ExecutorCompleted()

    def _check_budget(self) -> float:
        if self._executor_result is not None:
            raise _ExecutorCompleted()
        if self._poisoned:
            raise BudgetExceeded("Client is sealed after a timeout or budget violation; do not start another request")
        if self._started is None:
            raise RuntimeError("The task has not started")
        remaining = self.task_budget_s - (time.monotonic() - self._started)
        if remaining <= 0:
            raise BudgetExceeded("Task wall-clock budget exhausted")
        return remaining

    def _request(self, payload: dict) -> dict:
        remaining = self._check_budget()
        if self.model_calls >= self.max_model_calls:
            raise BudgetExceeded("Model request budget exhausted")
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        budget = estimate_input_budget(payload, self.max_output_tokens, self._last_measured_request)
        self._journal.emit("input_budget_checked", next_call_id=self.model_calls + 1, budget=budget)
        if not budget["within_context_budget"] or not budget["within_wire_limit"]:
            self._journal.artifact(f"model-{self.model_calls + 1:02d}-unsent-request.json", payload)
            self._journal.artifact(f"model-{self.model_calls + 1:02d}-unsent-budget.json", budget)
            self._journal.emit("input_budget_exceeded", budget=budget, measured_model_tokens=None)
            raise BudgetExceeded("Request exceeds the recorded conservative input budget; no silent truncation")
        self.model_calls += 1
        call_id = self.model_calls
        if self._format_correction_pending:
            self.format_correction_call_ids.append(call_id)
            self._format_correction_pending = False
            self._journal.emit("format_correction_dispatched", call_id=call_id,
                               counted_in_original_model_budget=True)
        timeout = min(self.request_timeout_s, remaining)
        self._journal.artifact(f"model-{call_id:02d}-request.json", payload)
        self._journal.artifact(f"model-{call_id:02d}-input-budget.json", budget)
        self._journal.emit("model_request", call_id=call_id, timeout_s=timeout,
                           request_bytes=len(encoded), input_budget=budget)
        started = time.monotonic()
        completed: queue.Queue = queue.Queue(maxsize=1)

        def worker():
            try:
                # Ignore machine proxy variables and reject redirects. No cloud
                # fallback, API-key environment lookup, or SDK automatic retry.
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
                request = urllib.request.Request(BASE_URL + "/chat/completions", data=encoded,
                                                 headers={"Content-Type": "application/json"}, method="POST")
                with opener.open(request, timeout=timeout) as response:
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("Model response exceeds 2 MiB cap")
                response_body = json.loads(raw)
                if not isinstance(response_body, dict):
                    raise ValueError("Model response must be a JSON object")
                self._journal.artifact(f"model-{call_id:02d}-response.json", response_body)
                completed.put((response_body, None))
            except Exception as exc:
                completed.put((None, exc))

        # A wall-clock wait, unlike per-read socket timeout. On timeout the daemon
        # has no access to tools and cannot start another request. The supervisor
        # owns process termination and confirming the model server is idle.
        thread = threading.Thread(target=worker, name=f"ollama-request-{call_id}", daemon=True)
        thread.start()
        try:
            response_body, error = completed.get(timeout=timeout)
        except queue.Empty:
            self._poisoned = True
            self._journal.emit("model_timeout", call_id=call_id, elapsed_s=time.monotonic() - started,
                               usage=None, usage_status="UNAVAILABLE", server_cancel_confirmed=False)
            raise BudgetExceeded("Model request wall-clock timeout; server cancellation is unconfirmed") from None
        elapsed = time.monotonic() - started
        if error is not None:
            self._journal.emit("model_error", call_id=call_id, elapsed_s=elapsed,
                               error_type=type(error).__name__, error=str(error),
                               http_status=getattr(error, "code", None), input_budget=budget,
                               usage=None, usage_status="UNAVAILABLE")
            raise error
        usage = response_body.get("usage")
        usage = usage if isinstance(usage, dict) else None
        self.usage.append({"call_id": call_id, "usage": usage,
                           "status": "REPORTED_BY_SERVER" if usage is not None else "UNAVAILABLE"})
        try:
            actual_prompt_tokens = check_reported_prompt_tokens(budget, usage)
        except InputBudgetViolation as exc:
            self._poisoned = True
            self._last_measured_request = None
            self._journal.emit("input_budget_violation", call_id=call_id, budget=budget,
                               actual_prompt_tokens=usage.get("prompt_tokens"), error=str(exc),
                               elapsed_s=elapsed, usage=usage,
                               response_discarded=True, context_expanded=False)
            raise
        self._journal.emit("model_response", call_id=call_id, elapsed_s=elapsed,
                           usage=usage, usage_status=self.usage[-1]["status"],
                           actual_prompt_tokens=actual_prompt_tokens, input_budget=budget)
        self._check_budget()
        self._last_measured_request = ({"payload": copy.deepcopy(payload),
                                        "prompt_tokens": actual_prompt_tokens, "call_id": call_id}
                                       if actual_prompt_tokens is not None else None)
        return response_body

    def run(self, messages: list[dict]) -> dict:
        if self._started is not None:
            raise RuntimeError("Each client may run only one task; budgets cannot be reset")
        if any(not isinstance(message.get("content"), str) for message in messages):
            raise ValueError("Only plain-text input messages are accepted")
        self._started = time.monotonic()
        self._journal.emit("task_started", messages=messages)
        latest: list[dict] = []
        status, error = "COMPLETED", None
        try:
            conversation = copy.deepcopy(messages)
            if self.max_format_corrections:
                # Already-complete trusted work needs no extra model request.
                self._after_tool_result()
            while True:
                turn: list[dict] = []
                for response in self._assistant.run(messages=conversation, lang="zh"):
                    turn = [item.model_dump() if isinstance(item, Message) else item for item in response]
                    latest = conversation[len(messages):] + turn
                    self._check_budget()
                if not turn or turn[-1].get("role") == "function" or turn[-1].get("function_call"):
                    raise BudgetExceeded("Framework loop ended before a final assistant response")
                if not self.max_format_corrections:
                    break
                # The callback is trusted state, never a model-written PASS.
                self._after_tool_result()
                self._journal.emit("framework_ended_with_pending_checks",
                                   model_call_id=self.model_calls, output=turn)
                if self.format_correction_attempts >= self.max_format_corrections:
                    status, error = "INCOMPLETE", "No executor completion after the one permitted format correction"
                    break
                self.format_correction_attempts += 1
                self._format_correction_pending = True
                correction = {"role": "user", "content": FORMAT_CORRECTION}
                # Keep the original reply verbatim as untrusted assistant data.
                # Only a later native tool_calls field can dispatch a tool.
                conversation = conversation + turn + [correction]
                self._journal.emit("format_correction_scheduled", message=correction,
                                   attempt=self.format_correction_attempts,
                                   max_model_calls=self.max_model_calls,
                                   budget_reset=False, prose_execution_enabled=False)
        except _ExecutorCompleted:
            status = "EXECUTOR_COMPLETED"
        except BudgetExceeded as exc:
            status, error = "STOPPED_LIMIT", str(exc)
        except Exception as exc:
            status, error = "ERROR", f"{type(exc).__name__}: {exc}"
        result = {"status": status, "messages": latest, "model_calls": self.model_calls,
                  "usage": self.usage, "elapsed_s": time.monotonic() - self._started, "error": error,
                  "format_correction_attempts": self.format_correction_attempts,
                  "format_correction_call_ids": self.format_correction_call_ids}
        if status == "EXECUTOR_COMPLETED":
            result["executor_result"] = copy.deepcopy(self._executor_result)
        self._journal.artifact("result.json", result)
        self._journal.emit("task_finished", **result)
        # Keep the log available for a late response artifact after a timeout;
        # ordinary runs have no remaining worker when this method returns.
        self._journal.events.close()
        return result
