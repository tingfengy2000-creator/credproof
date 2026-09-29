"""Local boundary/control-flow checks, never evidence of model inference."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from qwen_agent.llm.schema import Message
from qwen_agent.tools.base import BaseTool

from agent_pilot.model_client import (BudgetExceeded, InputBudgetViolation, LocalAgentClient,
                                     check_reported_prompt_tokens, estimate_input_budget,
                                     from_ollama_response, to_ollama_messages)


class SerializationTests(unittest.TestCase):
    def test_native_call_id_survives_tool_roundtrip(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": "Checking.", "tool_calls": [
            {"id": "call_abc", "type": "function", "function": {"name": "read_evidence", "arguments": '{"id":"e1"}'}}
        ]}}]}
        output = from_ollama_response(raw)
        wire = to_ollama_messages([{"role": "user", "content": "inspect"}, *output,
                                  {"role": "function", "content": "result", "name": "read_evidence",
                                   "extra": {"function_id": "call_abc"}}])
        self.assertEqual(wire[1]["tool_calls"], raw["choices"][0]["message"]["tool_calls"])
        self.assertEqual(wire[2], {"role": "tool", "tool_call_id": "call_abc", "content": "result"})

    def test_parallel_calls_keep_distinct_ids(self):
        raw = {"choices": [{"message": {"role": "assistant", "tool_calls": [
            {"id": name, "type": "function", "function": {"name": "read_evidence", "arguments": "{}"}}
            for name in ["call_1", "call_2"]
        ]}}]}
        wire = to_ollama_messages(from_ollama_response(raw))
        self.assertEqual([call["id"] for call in wire[0]["tool_calls"]], ["call_1", "call_2"])

    def test_no_tool_call_inferred_from_prose(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": '<tool_call>{"name":"shell"}</tool_call>'}}]}
        output = from_ollama_response(raw)
        self.assertIsNone(output[0].function_call)

    def test_missing_call_id_is_rejected(self):
        with self.assertRaises(ValueError):
            from_ollama_response({"choices": [{"message": {"role": "assistant", "tool_calls": [
                {"type": "function", "function": {"name": "read_evidence", "arguments": "{}"}}
            ]}}]})

    def test_file_content_is_rejected(self):
        with self.assertRaises(ValueError):
            to_ollama_messages([{"role": "user", "content": [{"file": "/some/file"}]}])

    def test_multiple_completion_choices_are_rejected(self):
        with self.assertRaises(ValueError):
            from_ollama_response({"choices": [{}, {}]})

    def test_plain_response_supports_no_tool_control(self):
        raw = {"choices": [{"message": {"role": "assistant", "content": '{"patch":"example"}'}}]}
        messages = from_ollama_response(raw)
        self.assertEqual(to_ollama_messages(messages), [{"role": "assistant", "content": '{"patch":"example"}'}])

    def test_conservative_input_cap_rejects_before_model_request(self):
        # This is a local pre-dispatch boundary test. No server or fake response.
        with tempfile.TemporaryDirectory() as folder:
            client = LocalAgentClient(tools=[], system_message="test", log_dir=Path(folder), max_output_tokens=8192)
            try:
                self.assertEqual(client.max_request_bytes, 7680)
                self.assertTrue(client._assistant.llm.use_raw_api)
                self.assertEqual(client._assistant.mem.system_files, [])
                self.assertEqual(client._assistant.function_map, {})
                client._started = time.monotonic()
                with self.assertRaises(BudgetExceeded):
                    client._request({"messages": [{"role": "user", "content": "x" * 7681}]})
                self.assertEqual(client.model_calls, 0)
            finally:
                client._journal.events.close()

    def test_seed_boundaries_and_transport_configuration(self):
        with tempfile.TemporaryDirectory() as folder:
            for invalid in (-1, 2**31, True, "1", 1.5):
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    LocalAgentClient(tools=[], system_message="test", log_dir=Path(folder), seed=invalid)
            client = LocalAgentClient(tools=[], system_message="test", log_dir=Path(folder), seed=3)
            try:
                self.assertEqual(client._assistant.llm.generate_cfg["seed"], 3)
                self.assertEqual(client.seed, 3)
                self.assertEqual(client.model_calls, 0)
            finally:
                client._journal.events.close()


class InputBudgetTests(unittest.TestCase):
    """Fabricated arithmetic inputs only; no model/server/response mock is used."""
    def setUp(self):
        self.payload = {
            "model": "qwen3-coder:30b", "stream": False, "max_tokens": 2048,
            "temperature": 0.2, "top_p": 0.8, "seed": 0,
            "messages": [{"role": "system", "content": "requirements"},
                         {"role": "user", "content": "inspect"}],
            "tools": [{"type": "function", "function": {"name": "read", "parameters": {}}}],
        }
        self.previous = {"payload": copy.deepcopy(self.payload), "prompt_tokens": 100, "call_id": 2}

    def extended(self):
        result = copy.deepcopy(self.payload)
        result["messages"] += [{"role": "assistant", "content": "检查"},
                               {"role": "tool", "tool_call_id": "fixture", "content": "{}"}]
        return result

    def test_first_request_uses_full_wire_bytes_and_global_reserve(self):
        budget = estimate_input_budget(self.payload, 2048)
        self.assertEqual(budget["method"], "UTF8_WIRE_BYTES")
        expected = len(json.dumps(self.payload, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(budget["input_token_upper_bound"], expected)
        self.assertEqual(budget["context_token_upper_bound"], expected + 2048 + 512)

    def test_exact_measured_prefix_counts_all_suffix_json_bytes_and_framing(self):
        payload = self.extended()
        budget = estimate_input_budget(payload, 2048, self.previous)
        suffix_bytes = len(json.dumps(payload["messages"][2:], ensure_ascii=False).encode("utf-8"))
        self.assertEqual(budget["method"], "MEASURED_PREFIX_PLUS_UTF8_SUFFIX")
        self.assertEqual(budget["prefix_call_id"], 2)
        self.assertEqual(budget["suffix_json_bytes"], suffix_bytes)
        self.assertEqual(budget["input_token_upper_bound"], 100 + suffix_bytes + 2 * 512)
        self.assertEqual(budget["context_token_upper_bound"], 100 + suffix_bytes + 2 * 512 + 2048 + 512)

    def test_changed_or_shortened_prefix_never_reuses_measurement(self):
        variants = [self.extended(), self.extended(), self.extended()]
        variants[0]["messages"][0]["content"] += " changed"
        variants[1]["messages"][1]["content"] += " appended to last prior message"
        variants[2]["messages"] = variants[2]["messages"][:1]
        for payload in variants:
            with self.subTest(messages=payload["messages"]):
                budget = estimate_input_budget(payload, 2048, self.previous)
                self.assertEqual(budget["method"], "UTF8_WIRE_BYTES")
                self.assertEqual(budget["reuse_reason"], "message_prefix_changed")

    def test_tools_model_generation_or_other_configuration_change_disables_reuse(self):
        variants = []
        for key, value in [("tools", []), ("model", "different-model"), ("seed", 1),
                           ("temperature", 0.3), ("max_tokens", 8192), ("format", "json")]:
            payload = self.extended()
            payload[key] = value
            variants.append(payload)
        omitted = self.extended()
        del omitted["tools"]
        variants.append(omitted)
        for payload in variants:
            budget = estimate_input_budget(payload, 2048, self.previous)
            self.assertEqual(budget["method"], "UTF8_WIRE_BYTES")
            self.assertEqual(budget["reuse_reason"], "request_configuration_changed")

    def test_invalid_or_missing_measurements_fall_back(self):
        for count in [None, 0, -1, True, 100.0, "100", 16385]:
            previous = dict(self.previous, prompt_tokens=count)
            budget = estimate_input_budget(self.extended(), 2048, previous)
            self.assertEqual(budget["method"], "UTF8_WIRE_BYTES")
        previous = dict(self.previous, payload={"messages": "not a list"})
        self.assertEqual(estimate_input_budget(self.payload, 2048, previous)["method"], "UTF8_WIRE_BYTES")

    def test_structural_comparison_preserves_types_but_ignores_dictionary_key_order(self):
        reordered = copy.deepcopy(self.payload)
        reordered["messages"][0] = {"content": "requirements", "role": "system"}
        self.assertEqual(estimate_input_budget(reordered, 2048, self.previous)["method"],
                         "MEASURED_PREFIX_PLUS_UTF8_SUFFIX")
        previous = copy.deepcopy(self.previous)
        previous["payload"]["seed"] = False  # False == 0 in Python, but not the same JSON primitive.
        self.assertEqual(estimate_input_budget(self.payload, 2048, previous)["method"], "UTF8_WIRE_BYTES")

    def test_measured_prefix_can_admit_history_without_removing_it_or_expanding_context(self):
        payload = copy.deepcopy(self.payload)
        payload["messages"][1]["content"] = "x" * 12000
        self.assertTrue(estimate_input_budget(payload, 2048)["within_context_budget"])
        previous = {"payload": copy.deepcopy(payload), "prompt_tokens": 3000, "call_id": 1}
        payload["messages"].append({"role": "assistant", "content": "y" * 3000})
        untouched = copy.deepcopy(payload)
        self.assertFalse(estimate_input_budget(payload, 2048)["within_context_budget"])
        budget = estimate_input_budget(payload, 2048, previous)
        self.assertTrue(budget["within_context_budget"])
        self.assertEqual(budget["context_token_limit"], 16384)
        self.assertEqual(payload, untouched)

    def test_context_and_absolute_wire_caps_still_reject(self):
        payload = self.extended()
        payload["messages"][-1]["content"] = "x" * 15000
        self.assertFalse(estimate_input_budget(payload, 2048, self.previous)["within_context_budget"])
        payload["messages"][-1]["content"] = "x" * 262145
        self.assertFalse(estimate_input_budget(payload, 2048, self.previous)["within_wire_limit"])

    def test_server_observation_above_bound_is_rejected_and_invalid_usage_not_reused(self):
        budget = estimate_input_budget(self.extended(), 2048, self.previous)
        self.assertEqual(check_reported_prompt_tokens(budget, {"prompt_tokens": 101}), 101)
        with self.assertRaises(InputBudgetViolation):
            check_reported_prompt_tokens(budget, {"prompt_tokens": budget["input_token_upper_bound"] + 1})
        for usage in [None, {}, {"prompt_tokens": 0}, {"prompt_tokens": True}, {"prompt_tokens": "101"}]:
            self.assertIsNone(check_reported_prompt_tokens(budget, usage))
        with self.assertRaises(InputBudgetViolation):
            check_reported_prompt_tokens(dict(budget, input_token_upper_bound=20000), {"prompt_tokens": 16384})


class ExecutionCompletionTests(unittest.TestCase):
    """Real FnCallAgent loop and tools; explicitly scripted LLM control fixture.

    No model, HTTP server, candidate code, or repair verdict is involved. The
    fixture only makes subsequent model/tool dispatch observable in these tests.
    """
    def run_fixture(self, completion=None, *, expire_in_tool=False, unknown=False):
        context = {"tools_dispatched": [], "model_dispatches": []}

        class CountingTool(BaseTool):
            description = "Unit-test in-memory side effect only."
            parameters = []

            def __init__(self, name):
                self.name = name
                super().__init__()

            def call(self, params, **kwargs):
                context["tools_dispatched"].append(self.name)
                if expire_in_tool:
                    context["client"]._started -= 1000
                return json.dumps({"test_fixture_tool": self.name})

        with tempfile.TemporaryDirectory() as folder:
            context["folder"] = Path(folder)
            callback = None if completion is None else lambda: completion(context)
            client = LocalAgentClient(tools=[CountingTool("first"), CountingTool("second")],
                                      system_message="UNIT TEST ONLY: no inference.", log_dir=Path(folder),
                                      execution_completion=callback)
            context["client"] = client

            def scripted_llm(**kwargs):
                context["model_dispatches"].append(copy.deepcopy(kwargs))
                if len(context["model_dispatches"]) == 1:
                    names = ["not_registered"] if unknown else ["first", "second"]
                    yield [Message(role="assistant", content="", function_call={"name": name, "arguments": "{}"},
                                   extra={"function_id": f"unit_fixture_{index}"})
                           for index, name in enumerate(names)]
                else:
                    yield [Message(role="assistant", content="UNIT_TEST_SCRIPTED_FINAL")]

            with patch.object(client._assistant, "_call_llm", new=scripted_llm), \
                    patch("agent_pilot.model_client.urllib.request.build_opener",
                          side_effect=AssertionError("Tests must not contact a model")):
                result = client.run([{"role": "user", "content": "Dispatch-control test fixture, not inference."}])
            context["events"] = [json.loads(line) for line in (Path(folder) / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            context["saved_result"] = json.loads((Path(folder) / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(client.model_calls, 0)  # Do not count fixture dispatch as actual model use.
            return result, context

    def test_terminal_stops_remaining_batch_and_next_model_after_actual_tool_audit(self):
        terminal = {"source": "UNIT_TEST_EXECUTOR", "terminal": True}
        observed_last_events = []

        def complete(context):
            events = [json.loads(line) for line in (context["folder"] / "events.jsonl").read_text(encoding="utf-8").splitlines()]
            observed_last_events.append(events[-1]["event"])
            self.assertEqual(context["tools_dispatched"], ["first"])
            return terminal

        result, context = self.run_fixture(complete)
        self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
        self.assertEqual(result["executor_result"], terminal)
        self.assertIsNone(result["error"])
        self.assertEqual(observed_last_events, ["tool_result"])
        self.assertEqual(context["tools_dispatched"], ["first"])
        self.assertEqual(len(context["model_dispatches"]), 1)
        self.assertEqual([e["name"] for e in context["events"] if e["event"] == "tool_result"], ["first"])
        self.assertTrue(all(m.get("function_call") for m in result["messages"]))
        self.assertNotIn("UNIT_TEST_SCRIPTED_FINAL", json.dumps(result["messages"]))
        self.assertEqual(context["saved_result"], result)
        terminal["terminal"] = False
        self.assertTrue(result["executor_result"]["terminal"])  # Snapshot, not mutable executor state.

    def test_no_callback_or_none_result_preserves_default_dispatch(self):
        for completion in [None, lambda context: None]:
            with self.subTest(callback_enabled=completion is not None):
                result, context = self.run_fixture(completion)
                self.assertEqual(result["status"], "COMPLETED")
                self.assertNotIn("executor_result", result)
                self.assertEqual(context["tools_dispatched"], ["first", "second"])
                self.assertEqual(len(context["model_dispatches"]), 2)
                self.assertEqual(result["messages"][-1]["content"], "UNIT_TEST_SCRIPTED_FINAL")

    def test_callback_errors_are_not_swallowed_or_reclassified_as_completion(self):
        for error_type in [ValueError, BudgetExceeded]:
            def fail(context):
                raise error_type("unit callback failure")
            with self.subTest(error_type=error_type.__name__):
                result, context = self.run_fixture(fail)
                self.assertEqual(result["status"], "ERROR")
                self.assertNotIn("executor_result", result)
                self.assertIn("unit callback failure", result["error"])
                self.assertEqual(context["tools_dispatched"], ["first"])
                self.assertEqual(len(context["model_dispatches"]), 1)
                self.assertTrue(any(e["event"] == "execution_completion_error" for e in context["events"]))

    def test_invalid_callback_values_fail_closed(self):
        for value in [False, [], {}, {"bad": float("nan")}, {"bad": object()}]:
            with self.subTest(value_type=type(value).__name__):
                result, context = self.run_fixture(lambda current: value)
                self.assertEqual(result["status"], "ERROR")
                self.assertNotIn("executor_result", result)
                self.assertEqual(context["tools_dispatched"], ["first"])
                self.assertEqual(len(context["model_dispatches"]), 1)

    def test_completion_precedes_post_tool_budget_check(self):
        result, context = self.run_fixture(lambda current: {"terminal": True}, expire_in_tool=True)
        self.assertEqual(result["status"], "EXECUTOR_COMPLETED")
        self.assertEqual(context["tools_dispatched"], ["first"])
        self.assertEqual(len(context["model_dispatches"]), 1)

    def test_unknown_tool_does_not_invoke_execution_completion(self):
        def unexpected(context):
            raise AssertionError("An unregistered tool is not a real tool execution")
        result, context = self.run_fixture(unexpected, unknown=True)
        self.assertEqual(result["status"], "COMPLETED")
        self.assertEqual(context["tools_dispatched"], [])
        self.assertEqual(len(context["model_dispatches"]), 2)
        self.assertFalse(any(e["event"] == "execution_completion_checked" for e in context["events"]))


if __name__ == "__main__":
    unittest.main()
