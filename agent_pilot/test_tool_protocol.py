"""REPLAY/control tests: mock HTTP, real adapter/FnCallAgent/budget code.

Historical h05/h06 responses are replayed verbatim. Later responses are explicit
control fixtures, NOT new model inference, repair results, or isolation evidence.
No tool in this file reads files, executes candidate code, or contacts a service.
"""
import copy
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from agent_pilot.model_client import BASE_URL, FORMAT_CORRECTION, LocalAgentClient, from_ollama_response
from agent_pilot.tools import StrictTool, code_path


ROOT = Path(__file__).resolve().parents[1]
RECORDS = ROOT / "experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison"
DELAY = object()


def original(case, kind="response"):
    return json.loads((RECORDS / case / "C-agent/model" / f"model-01-{kind}.json").read_text(encoding="utf-8"))


def native(name="read_code", arguments='{"path":"tool.py"}', *, second=False):
    calls = [{"id": "REPLAY_ONLY_call_1", "type": "function", "function": {"name": name, "arguments": arguments}}]
    if second:
        calls.append({"id": "REPLAY_ONLY_call_2", "type": "function",
                      "function": {"name": "read_code", "arguments": arguments}})
    return {"choices": [{"message": {"role": "assistant", "content": "", "tool_calls": calls},
                         "finish_reason": "tool_calls"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}


def plain(content="REPLAY_ONLY ordinary answer; not an executor completion"):
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110}}


class ReplayTransport:
    """In-memory HTTP replacement; never calls urllib or a real model."""
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []
        self.release = threading.Event()
        self.threads = []

    def open(self, request, timeout):
        self.threads.append(threading.current_thread())
        if request.full_url != BASE_URL + "/chat/completions" or request.method != "POST":
            raise AssertionError("Unexpected REPLAY transport destination")
        self.requests.append(json.loads(request.data))
        if not self.replies:
            raise AssertionError("REPLAY fixture exhausted: unexpected extra request")
        reply = self.replies.pop(0)
        if reply is DELAY:
            self.release.wait(2)
            reply = native()
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply, ensure_ascii=False).encode("utf-8"))


class ToolProtocolReplayTests(unittest.TestCase):
    def exercise(self, replies, *, case="h05", corrections=1, limit=12,
                 complete_on_read=False, terminal_at_start=False, no_tools=False,
                 request_timeout=120):
        transport = ReplayTransport(replies)
        effects, audit = [], []
        state = {"terminal": {"kind": "REPLAY_ONLY_TERMINAL"} if terminal_at_start else None}

        def read(args):
            code_path(args["path"])
            effects.append(args["path"])
            if complete_on_read and len(effects) >= int(complete_on_read):
                state["terminal"] = {"kind": "REPLAY_ONLY_TERMINAL", "after": "in_memory_tool"}
            return {"kind": "REPLAY_ONLY_TOOL_RESULT", "source": "No real file was read."}

        tool = StrictTool("read_code", "REPLAY-only in-memory tool; no source execution.",
                          {"path": {"type": "string"}}, ["path"], read, audit)
        request = original(case, "request")
        with tempfile.TemporaryDirectory(prefix="credproof-tool-REPLAY-") as folder:
            client = LocalAgentClient(tools=[] if no_tools else [tool],
                                      system_message=request["messages"][0]["content"], log_dir=Path(folder),
                                      max_model_calls=limit, max_format_corrections=corrections,
                                      request_timeout_s=request_timeout,
                                      execution_completion=None if no_tools else lambda: state["terminal"])
            try:
                with patch("agent_pilot.model_client.urllib.request.build_opener", return_value=transport):
                    result = client.run(copy.deepcopy(request["messages"][1:]))
            finally:
                # Let a deliberately delayed mock worker finish before tmp cleanup.
                transport.release.set()
                for worker in transport.threads:
                    worker.join(timeout=2)
                    self.assertFalse(worker.is_alive(), "REPLAY worker did not end")
            events = [json.loads(line) for line in (Path(folder) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            saved = json.loads((Path(folder) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(saved, result)
            self.assertEqual(client.model_calls, len(transport.requests))
            self.assertTrue(all(payload["stream"] is False for payload in transport.requests))
        return result, transport.requests, effects, audit, events

    def test_original_h05_h06_are_content_not_native_calls(self):
        for case in ("h05", "h06"):
            with self.subTest(case=case):
                response = original(case)
                message = response["choices"][0]["message"]
                self.assertNotIn("tool_calls", message)
                self.assertTrue(message["content"].startswith("<function=read_code>"))
                self.assertNotIn("<tool_call>", message["content"])
                converted = from_ollama_response(response)
                self.assertTrue(all(item.function_call is None for item in converted))
                self.assertEqual(converted[0].content, message["content"])

    def test_one_correction_can_dispatch_later_native_call_and_keep_original(self):
        for case in ("h05", "h06"):
            with self.subTest(case=case):
                raw = original(case)
                result, requests, effects, audit, events = self.exercise(
                    [raw, native()], case=case, complete_on_read=True)
                self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
                self.assertEqual(result["model_calls"], 2)  # Counted mock HTTP dispatch, not actual inference.
                self.assertEqual(result["format_correction_attempts"], 1)
                self.assertEqual(result["format_correction_call_ids"], [2])
                self.assertEqual(effects, ["tool.py"])
                self.assertEqual(len(audit), 1)
                self.assertEqual(requests[1]["messages"][:len(requests[0]["messages"])], requests[0]["messages"])
                self.assertEqual(requests[1]["messages"][-2], raw["choices"][0]["message"])
                self.assertEqual(requests[1]["messages"][-1], {"role": "user", "content": FORMAT_CORRECTION})
                self.assertEqual(requests[0]["tools"], requests[1]["tools"])
                self.assertIn(raw["choices"][0]["message"]["content"], [m.get("content") for m in result["messages"]])
                decoded = [event for event in events if event["event"] == "native_response_decoded"]
                self.assertEqual(len(decoded), 2)

    def test_repeated_plain_call_text_remains_incomplete_and_is_never_executed(self):
        result, requests, effects, _, _ = self.exercise([original("h05"), original("h06")])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["format_correction_attempts"], 1)
        self.assertEqual(result["format_correction_call_ids"], [2])
        self.assertEqual(effects, [])

    def test_correction_preserves_full_prior_native_history_without_redispatch(self):
        # Two real adapter/tool paths, but mocked HTTP and in-memory tool effects.
        first = native()
        later = native()
        later["choices"][0]["message"]["tool_calls"][0]["id"] = "REPLAY_ONLY_later_call"
        ordinary = plain("REPLAY_ONLY final text before the executor is complete")
        result, requests, effects, audit, events = self.exercise(
            [first, ordinary, later], complete_on_read=2)
        self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
        self.assertEqual(result["model_calls"], 3)
        self.assertEqual(result["format_correction_attempts"], 1)
        self.assertEqual(result["format_correction_call_ids"], [3])
        self.assertEqual(effects, ["tool.py", "tool.py"])
        self.assertEqual(len(audit), 2)  # Prior native call was not redispatched.
        history = requests[2]["messages"]
        self.assertEqual(history[:len(requests[1]["messages"])], requests[1]["messages"])
        self.assertEqual([m["role"] for m in history],
                         ["system", "user", "assistant", "tool", "assistant", "user"])
        self.assertEqual(history[2]["tool_calls"], first["choices"][0]["message"]["tool_calls"])
        self.assertEqual(history[3]["tool_call_id"], "REPLAY_ONLY_call_1")
        self.assertEqual(json.loads(history[3]["content"]), audit[0]["result"])
        self.assertEqual(history[4], ordinary["choices"][0]["message"])
        self.assertEqual(history[5], {"role": "user", "content": FORMAT_CORRECTION})
        prior_functions = [m for m in result["messages"] if m["role"] == "function"]
        self.assertEqual(len(prior_functions), 1)
        self.assertEqual(prior_functions[0]["extra"]["function_id"], "REPLAY_ONLY_call_1")
        self.assertEqual(len([e for e in events if e["event"] == "tool_request"]), 2)

    def test_budget_one_does_not_dispatch_planned_correction(self):
        result, requests, effects, _, _ = self.exercise([original("h05")], limit=1)
        self.assertEqual(result["status"], "STOPPED_LIMIT")
        self.assertEqual(len(requests), 1)
        self.assertEqual(result["format_correction_attempts"], 1)
        self.assertEqual(result["format_correction_call_ids"], [])
        self.assertEqual(effects, [])

    def test_budget_two_does_not_reset_after_correction_tool_dispatch(self):
        result, requests, effects, _, _ = self.exercise([original("h05"), native()], limit=2)
        self.assertEqual(result["status"], "STOPPED_LIMIT")
        self.assertEqual(len(requests), 2)
        self.assertEqual(result["format_correction_call_ids"], [2])
        self.assertEqual(effects, ["tool.py"])

    def test_terminal_prevents_model_request_or_correction(self):
        result, requests, effects, _, _ = self.exercise([], terminal_at_start=True)
        self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
        self.assertEqual(requests, [])
        self.assertEqual(effects, [])
        self.assertEqual(result["format_correction_attempts"], 0)

    def test_terminal_after_first_native_call_stops_batch_and_needs_no_correction(self):
        result, requests, effects, _, _ = self.exercise([native(second=True)], complete_on_read=True)
        self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
        self.assertEqual(len(requests), 1)
        self.assertEqual(effects, ["tool.py"])
        self.assertEqual(result["format_correction_attempts"], 0)

    def test_timeout_is_sealed_without_correction_or_late_tool_execution(self):
        result, requests, effects, _, events = self.exercise([DELAY], request_timeout=.02)
        self.assertEqual(result["status"], "STOPPED_LIMIT")
        self.assertEqual(len(requests), 1)
        self.assertEqual(effects, [])
        self.assertEqual(result["format_correction_attempts"], 0)
        self.assertTrue(any(item["event"] == "model_timeout" for item in events))

    def test_http_error_does_not_trigger_format_correction(self):
        error = HTTPError(BASE_URL + "/chat/completions", 503, "REPLAY_ONLY unavailable", {}, None)
        result, requests, effects, _, _ = self.exercise([error])
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(len(requests), 1)
        self.assertEqual(effects, [])
        self.assertEqual(result["format_correction_attempts"], 0)

    def test_default_zero_preserves_one_plain_response_without_execution(self):
        result, requests, effects, _, _ = self.exercise([original("h05")], corrections=0)
        self.assertEqual(result["status"], "COMPLETED")  # Framework status, not task success.
        self.assertEqual(len(requests), 1)
        self.assertEqual(effects, [])
        self.assertEqual(result["format_correction_attempts"], 0)

    def test_no_tools_control_does_not_get_extra_call(self):
        result, requests, _, _, _ = self.exercise([plain('{"diagnosis":"REPLAY_ONLY"}')],
                                                 corrections=0, no_tools=True, limit=1)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(len(requests), 1)
        self.assertNotIn("tools", requests[0])
        self.assertEqual(result["format_correction_attempts"], 0)

    def test_correction_requires_bounded_integer_tools_and_callback(self):
        with tempfile.TemporaryDirectory() as folder:
            for value in (-1, 2, True, 1.0, "1"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    LocalAgentClient(tools=[], system_message="REPLAY", log_dir=Path(folder), max_format_corrections=value)
            with self.assertRaises(ValueError):
                LocalAgentClient(tools=[], system_message="REPLAY", log_dir=Path(folder),
                                 max_format_corrections=1, execution_completion=lambda: None)

    def test_unknown_tool_is_rejected_even_after_correction(self):
        result, requests, effects, audit, events = self.exercise(
            [original("h05"), native("not_registered"), plain()])
        self.assertEqual(result["status"], "INCOMPLETE")
        self.assertEqual(len(requests), 3)
        self.assertEqual(effects, [])
        self.assertEqual(audit, [])
        tool_results = [item for item in events if item["event"] == "tool_result"]
        self.assertEqual(json.loads(tool_results[0]["result"])["error"], "tool_not_allowed")
        self.assertEqual(result["format_correction_call_ids"], [2])

    def test_invalid_arguments_and_paths_still_rejected_after_correction(self):
        for arguments in ('{"path":"../judge.py"}', '{"path":"tool.py","extra":true}',
                          '{"path":9}', '{}', 'not-json'):
            with self.subTest(arguments=arguments):
                result, requests, effects, audit, _ = self.exercise(
                    [original("h05"), native(arguments=arguments), plain()])
                self.assertEqual(result["status"], "INCOMPLETE")
                self.assertEqual(len(requests), 3)
                self.assertEqual(effects, [])
                self.assertEqual(audit[0]["result"]["status"], "REJECTED")


if __name__ == "__main__":
    unittest.main()
