"""Generate AI repair patches for every benchmark target and check each one (protocol bench-v1).

For each target x model x sample k (k = 1..3, seed = k):
  round 0  prompt = repair-v1 with the vulnerable tool, its checker findings and the tests
  round 1  only if round 0 did not PASS: same template with the round-0 patch and its findings
Every request, raw response, extraction result and checker record is saved; nothing is
filtered, retried or re-sampled. Requires a local Ollama; never uses a paid API.

    python scripts/bench/generate.py --model qwen2.5-coder:32b-instruct-q4_K_M --model qwen3-coder:30b \
        --output experiments/bench-v1/<run-id>
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from check_variant import check  # noqa: E402


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def run_check(target: Path, source: Path, label: str, out: Path) -> dict:
    report, record = check(target, source, label)
    common.write_json(out.with_suffix(".report.json"), report)
    common.write_json(out, record)
    return record


def one_round(args, target, model, k, rnd, source_text, findings_text, patch_dir):
    prompt = common.fill(common.template("repair-v1"), findings=findings_text, source=source_text.rstrip("\n"),
                         tests=common.tests_text(target).rstrip("\n"))
    options = dict(common.GEN_OPTIONS, seed=k)
    common.write_json(patch_dir / "request.json", {"protocol": common.PROTOCOL, "template": "repair-v1", "model": model,
                                                   "options": options, "prompt": prompt, "prompt_sha256": common.sha(prompt)})
    started = time.time()
    try:
        response = common.ollama_chat(args.host, model, prompt, options)
        error = None
    except Exception as exc:
        response, error = {}, f"{type(exc).__name__}: {exc}"
    common.write_json(patch_dir / "response.json", {"model": model, "error": error, "seconds": round(time.time() - started, 2),
                                                    "raw": response})
    text = ((response.get("message") or {}).get("content")) if response else None
    code, extraction = common.extract(text or "") if text is not None else (None, {"status": "NO_RESPONSE", "error": error})
    common.write_json(patch_dir / "extraction.json", extraction)
    record = None
    if code is not None:
        (patch_dir / "patch.py").write_text(code, encoding="utf-8", newline="\n")
        record = run_check(target, patch_dir / "patch.py", patch_dir.name, patch_dir / "check.json")
    return code, extraction, record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--host", default=os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434"))
    parser.add_argument("--target", action="append", help="limit to these target ids (default: all)")
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("new output directory required")
    args.output.mkdir(parents=True)
    selected = [t for t in common.targets() if not args.target or t.name in args.target]
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=common.ROOT, capture_output=True, text=True).stdout.strip()
    run = {"schema": "credproof.bench-run/v1", "protocol": common.PROTOCOL, "started_at": now(), "source_commit": commit,
           "host": platform.platform(), "python": platform.python_version(), "ollama": args.host,
           "models": [common.model_info(args.host, m) for m in args.model], "targets": [t.name for t in selected],
           "samples": common.SAMPLES, "generation_options": common.GEN_OPTIONS,
           "prompt_sha256": {"repair-v1": common.sha(common.template("repair-v1"))}}
    common.write_json(args.output / "run.json", run)

    baseline = {}
    for target in selected:
        baseline[target.name] = run_check(target, target / "project/tool.py", "vulnerable",
                                          args.output / "baseline" / f"{target.name}.json")
    for target in selected:
        vulnerable = (target / "project/tool.py").read_text(encoding="utf-8")
        for model in args.model:
            for k in range(1, common.SAMPLES + 1):
                base_id = f"{target.name}__{common.slug(model)}__s{k}"
                code0, ext0, rec0 = one_round(args, target, model, k, 0, vulnerable,
                                              common.findings(baseline[target.name]), args.output / "patches" / f"{base_id}__r0")
                print(f"{base_id}__r0 {ext0['status']} {rec0 and rec0['verdict']}", flush=True)
                if rec0 is not None and rec0["verdict"] == "PASS":
                    continue
                if code0 is None:
                    source1, note = vulnerable, f"the previous answer contained no usable tool.py ({ext0['status']})"
                    text1 = common.findings(baseline[target.name], note)
                else:
                    source1, text1 = code0, common.findings(rec0)
                _, ext1, rec1 = one_round(args, target, model, k, 1, source1, text1, args.output / "patches" / f"{base_id}__r1")
                print(f"{base_id}__r1 {ext1['status']} {rec1 and rec1['verdict']}", flush=True)
    run["finished_at"] = now()
    common.write_json(args.output / "run.json", run)


if __name__ == "__main__":
    main()
