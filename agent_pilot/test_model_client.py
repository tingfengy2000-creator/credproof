"""Pure serialization checks, not a claim that a model service was reached."""
import tempfile
import time
import unittest
from pathlib import Path

from agent_pilot.model_client import BudgetExceeded, LocalAgentClient, from_ollama_response, to_ollama_messages


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


if __name__ == "__main__":
    unittest.main()
