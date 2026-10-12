"""Shared, frozen helpers for the CredProof benchmark (protocol bench-v1).

Every run script uses these so that prompt filling, code extraction and
findings text are identical on every host.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "examples/bench"
PROMPTS = ROOT / "docs/bench/prompts"
PROTOCOL = "bench-v1"
GEN_OPTIONS = {"temperature": 0.7, "top_p": 0.95, "num_ctx": 16384, "num_predict": 2048}
JUDGE_OPTIONS = {"temperature": 0.0, "top_p": 1.0, "num_ctx": 16384, "num_predict": 512, "seed": 0}
SAMPLES = 3

FENCE = re.compile(r"```[ \t]*(?:python|py)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```", re.S)


def sha(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def targets() -> list[Path]:
    return sorted(p for p in BENCH.iterdir() if (p / "meta.json").is_file())


def slug(model: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", model.lower()).strip("-")


def template(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def tests_text(target: Path) -> str:
    return "\n\n".join(p.read_text(encoding="utf-8") for p in sorted((target / "project/tests").glob("test_*.py")))


def fill(text: str, **values: str) -> str:
    """Placeholder substitution without str.format (prompts contain braces)."""
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def extract(response: str) -> tuple[str | None, dict]:
    """Exactly one fenced python block, or a response that is itself valid Python."""
    blocks = FENCE.findall(response or "")
    if len(blocks) == 1:
        code, method = blocks[0] + "\n", "single_fenced_block"
    elif len(blocks) > 1:
        return None, {"status": "MULTIPLE_BLOCKS", "blocks": len(blocks)}
    else:
        code, method = response, "whole_response"
    if not code or not code.strip():
        return None, {"status": "NO_CODE"}
    try:
        ast.parse(code)
    except SyntaxError as exc:
        status = "SYNTAX_ERROR" if method == "single_fenced_block" else "NO_CODE"
        return (code if status == "SYNTAX_ERROR" else None), {"status": status, "method": method,
                                                              "error": f"{type(exc).__name__}: {exc.msg} (line {exc.lineno})"}
    return code, {"status": "OK", "method": method, "sha256": sha(code)}


def findings(record: dict | None, note: str = "") -> str:
    """Plain-text checker findings from a bench-check/v1 record (no secrets, no paths)."""
    if record is None:
        return "- " + (note or "no checker result is available")
    p = record.get("pytest") or {}
    lines = [f"- verdict: {record.get('verdict')}",
             f"- failed conditions: {', '.join(record.get('failed_checks') or []) or 'none'}",
             f"- credential observed in: {', '.join(record.get('leak_channels') or []) or 'nowhere'}",
             f"- reads inside the forbidden directory: {record.get('forbidden_reads', 0)}",
             f"- requests received by the forbidden service: {record.get('forbidden_service_receipts', 0)}",
             f"- business tests: {p.get('passed')} passed, {p.get('failed')} failed"]
    if record.get("reason"):
        lines.append(f"- incomplete evidence: {record['reason']}")
    if note:
        lines.append("- " + note)
    return "\n".join(lines)


def ollama_chat(host: str, model: str, prompt: str, options: dict, timeout: float = 600) -> dict:
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}],
                       "stream": False, "options": options}).encode("utf-8")
    request = urllib.request.Request(host.rstrip("/") + "/api/chat", data=body,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def model_info(host: str, model: str) -> dict:
    body = json.dumps({"model": model}).encode("utf-8")
    request = urllib.request.Request(host.rstrip("/") + "/api/show", data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        return {"name": model, "details": data.get("details"), "modified_at": data.get("modified_at"),
                "digest": data.get("digest") or (data.get("model_info") or {}).get("general.file_type")}
    except Exception as exc:  # recorded, never silently ignored
        return {"name": model, "error": f"{type(exc).__name__}: {exc}"}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
