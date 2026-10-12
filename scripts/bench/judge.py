"""LLM-as-judge baseline (protocol bench-v1): ask local models whether each patch should be accepted.

Judged items: every extracted patch in the run, plus each target's vulnerable original
and reference fix (sanity anchors). The judge sees code and tests only, never
CredProof's findings. temperature 0, seed 0, one answer per (item, judge); unparsable
answers are recorded as INVALID, not retried.

    python scripts/bench/judge.py --run experiments/bench-v1/<run-id> --judge qwen2.5-coder:32b-instruct-q4_K_M
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402


def parse(text: str) -> dict:
    for match in re.finditer(r"\{.*?\}", text or "", re.S):
        try:
            value = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("verdict") in ("ACCEPT", "REJECT"):
            reasons = value.get("reasons") if isinstance(value.get("reasons"), list) else []
            return {"verdict": value["verdict"], "reasons": [str(r) for r in reasons][:8]}
    return {"verdict": "INVALID", "reasons": []}


def items(run: Path):
    for target in common.targets():
        yield f"{target.name}__vulnerable", target, target / "project/tool.py"
        yield f"{target.name}__reference", target, target / "reference_fix.py"
    for patch in sorted((run / "patches").glob("*/patch.py")):
        yield patch.parent.name, common.BENCH / patch.parent.name.split("__")[0], patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--judge", action="append", required=True)
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434"))
    args = parser.parse_args()
    for judge in args.judge:
        out_dir = args.run / "judges" / common.slug(judge)
        if out_dir.exists():
            raise SystemExit(f"judge output already exists: {out_dir}")
        common.write_json(out_dir / "judge.json", {"protocol": common.PROTOCOL, "model": common.model_info(args.host, judge),
                                                   "options": common.JUDGE_OPTIONS,
                                                   "prompt_sha256": common.sha(common.template("judge-v1"))})
        for item_id, target, source in items(args.run):
            prompt = common.fill(common.template("judge-v1"),
                                 original=(target / "project/tool.py").read_text(encoding="utf-8").rstrip("\n"),
                                 candidate=source.read_text(encoding="utf-8").rstrip("\n"),
                                 tests=common.tests_text(target).rstrip("\n"))
            started = time.time()
            try:
                response = common.ollama_chat(args.host, judge, prompt, common.JUDGE_OPTIONS)
                text, error = (response.get("message") or {}).get("content", ""), None
            except Exception as exc:
                response, text, error = {}, "", f"{type(exc).__name__}: {exc}"
            result = parse(text)
            common.write_json(out_dir / f"{item_id}.json", {"item": item_id, "source_sha256": common.sha(source.read_bytes()),
                                                            "prompt_sha256": common.sha(prompt), "seconds": round(time.time() - started, 2),
                                                            "error": error, **result, "raw": text})
            print(f"{common.slug(judge)} {item_id} {result['verdict']}", flush=True)


if __name__ == "__main__":
    main()
