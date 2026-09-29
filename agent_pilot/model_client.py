"""Qwen-Agent Assistant with a local-only, audited Ollama transport.

The official Assistant/FnCallAgent loop remains in use. We override its optional
knowledge path and TextChatAtOAI._chat_stream only; the latter yields one complete
native-tool-call result, preserving raw responses and real usage when available.
This client does not execute arbitrary commands or determine repair correctness.
"""
from __future__ import annotations

import copy
import json
import queue
import threading
import time
import urllib.request
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

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


class BudgetExceeded(RuntimeError):
    """No more actions may be dispatched by this task."""


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
        payload = {"model": MODEL, "messages": to_ollama_messages(messages),
                   "stream": False, **generate_cfg}
        yield from [from_ollama_response(self.owner._request(payload))]


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
        self.owner._check_budget()
        return result


class LocalAgentClient:
    """One client = one task. Use only caller-created, bounded BaseTool objects.

    Network timeout stops the client and refuses further calls. It does not prove
    server generation stopped. The supervisor must enforce the process deadline
    and reset/confirm idle Ollama before starting a new task after a timeout.
    """
    def __init__(self, *, tools: Sequence[BaseTool], system_message: str,
                 log_dir: Path, max_model_calls: int = 12,
                 request_timeout_s: float = 120, task_budget_s: float = 900,
                 max_output_tokens: int = 2048, seed: int = 0):
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
        self.max_model_calls = max_model_calls
        self.request_timeout_s = request_timeout_s
        self.task_budget_s = task_budget_s
        self.max_output_tokens = max_output_tokens
        self.seed = seed
        # A deliberately conservative wire-byte gate, not measured model tokens.
        # Model/service context length is configured externally to 16,384 tokens.
        self.max_request_bytes = min(MAX_REQUEST_BYTES, CONTEXT_TOKENS - max_output_tokens - TEMPLATE_RESERVE)
        self.model_calls = 0
        self.usage: list[dict] = []
        self._started: float | None = None
        self._poisoned = False
        self._journal = _Journal(Path(log_dir))
        self._assistant = _RestrictedAssistant(self, llm=_LocalModel(self),
                                               function_list=list(tools), system_message=system_message)
        self._journal.emit("client_created", framework="qwen-agent", framework_version=version("qwen-agent"),
                           model=MODEL, base_url=BASE_URL, tools=[tool.function for tool in tools],
                           max_model_calls=max_model_calls, request_timeout_s=request_timeout_s,
                           task_budget_s=task_budget_s, max_output_tokens=max_output_tokens, seed=seed,
                           max_request_bytes=self.max_request_bytes, input_budget_kind="CONSERVATIVE_UTF8_WIRE_BYTES",
                           automatic_retries=0, knowledge_files_enabled=False)

    def _check_budget(self) -> float:
        if self._poisoned:
            raise BudgetExceeded("Client is sealed after a timeout; do not start another request")
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
        if len(encoded) > self.max_request_bytes:
            self._journal.emit("input_budget_exceeded", request_bytes=len(encoded),
                               max_request_bytes=self.max_request_bytes,
                               input_budget_kind="CONSERVATIVE_UTF8_WIRE_BYTES", measured_model_tokens=None)
            raise BudgetExceeded(f"Request exceeds the conservative {self.max_request_bytes}-byte input cap; no silent truncation")
        self.model_calls += 1
        call_id = self.model_calls
        timeout = min(self.request_timeout_s, remaining)
        self._journal.artifact(f"model-{call_id:02d}-request.json", payload)
        self._journal.emit("model_request", call_id=call_id, timeout_s=timeout, request_bytes=len(encoded))
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
                               usage=None, usage_status="UNAVAILABLE")
            raise error
        usage = response_body.get("usage")
        usage = usage if isinstance(usage, dict) else None
        self.usage.append({"call_id": call_id, "usage": usage,
                           "status": "REPORTED_BY_SERVER" if usage is not None else "UNAVAILABLE"})
        self._journal.emit("model_response", call_id=call_id, elapsed_s=elapsed,
                           usage=usage, usage_status=self.usage[-1]["status"])
        self._check_budget()
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
            for response in self._assistant.run(messages=messages, lang="zh"):
                latest = [item.model_dump() if isinstance(item, Message) else item for item in response]
                self._check_budget()
            if not latest or latest[-1].get("role") == "function" or latest[-1].get("function_call"):
                raise BudgetExceeded("Framework loop ended before a final assistant response")
        except BudgetExceeded as exc:
            status, error = "STOPPED_LIMIT", str(exc)
        except Exception as exc:
            status, error = "ERROR", f"{type(exc).__name__}: {exc}"
        result = {"status": status, "messages": latest, "model_calls": self.model_calls,
                  "usage": self.usage, "elapsed_s": time.monotonic() - self._started, "error": error}
        self._journal.artifact("result.json", result)
        self._journal.emit("task_finished", **result)
        # Keep the log available for a late response artifact after a timeout;
        # ordinary runs have no remaining worker when this method returns.
        self._journal.events.close()
        return result
