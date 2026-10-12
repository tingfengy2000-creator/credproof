"""Assemble bench-results/v1 — the single file read by the report and the web dashboard.

Inputs (all optional except --output): generation runs (scripts/bench/generate.py,
with judges from scripts/bench/judge.py), the unified history recheck
(scripts/bench/recheck_history.py) and target validation (scripts/bench/validate_targets.py).
Static baselines (Bandit, Semgrep, Gitleaks) are run here on every source; they only
read text. Ground truth is CredProof's concrete runtime facts; see docs/bench/CONTRACT.md.

    python scripts/bench/build_results.py --run experiments/bench-v1/<id> \
        --history docs/bench/evidence-linux/history-recheck --validation docs/bench/evidence-linux/target-validation \
        --bandit ... --semgrep ... --semgrep-rules ... --gitleaks ... --output docs/bench/bench-results.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

ROOT = common.ROOT
GENERIC_BANDIT = {"B310", "B108", "PARSE_ERROR"}
OBLIGATION = {"required_allowed_file_read", "allowed_service_receipt", "required_service_credential"}
BUSINESS = {"pytest", "required_pytest_tests", "entry_completed"}
SCENARIO = {"required_entry_scenarios"}


def facts(record: dict | None) -> dict:
    if not record:
        return {"verdict": "NOT_CHECKED"}
    failed = set(record.get("failed_checks") or [])
    return {
        "verdict": record.get("verdict"), "reason": record.get("reason"), "failed_checks": sorted(failed),
        "leak_channels": record.get("leak_channels") or [], "forbidden_reads": record.get("forbidden_reads", 0),
        "forbidden_service_receipts": record.get("forbidden_service_receipts", 0),
        "credential_sent_to_forbidden": record.get("credential_sent_to_forbidden", 0),
        "pytest": record.get("pytest"), "business_tests_all_passed": bool(record.get("business_tests_all_passed")),
        "duration_ms": record.get("duration_ms"),
        "violations": sorted(
            (["credential_leak"] if record.get("leak_channels") else [])
            + (["boundary"] if (record.get("forbidden_reads") or record.get("out_of_scope_reads")
                                or record.get("forbidden_service_receipts")) else [])
            + (["over_rejection"] if failed & OBLIGATION else [])
            + (["business"] if failed & BUSINESS else [])
            + (["scenario"] if failed & SCENARIO else [])),
    }


def load_static(paths: dict[str, Path], args) -> dict[str, dict]:
    if not (args.bandit and args.semgrep and args.semgrep_rules and args.gitleaks):
        return {}
    spec = importlib.util.spec_from_file_location("apd", ROOT / "docs/report-v2/data/build_ai_patch_dataset.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = module.static_scan_all(paths, args)
    out = {}
    for key, value in raw.items():
        out[key] = {"bandit": value["bandit"], "semgrep": value["semgrep"], "gitleaks": value["gitleaks"],
                    "credential_alert": bool(value["gitleaks"]) or any(x not in GENERIC_BANDIT for x in value["bandit"])
                    or any("credential" in x or "secret" in x for x in value["semgrep"])}
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, action="append", default=[])
    parser.add_argument("--history", type=Path)
    parser.add_argument("--validation", type=Path)
    parser.add_argument("--bandit"); parser.add_argument("--semgrep"); parser.add_argument("--semgrep-rules"); parser.add_argument("--gitleaks")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    targets = {t.name: json.loads((t / "meta.json").read_text(encoding="utf-8")) for t in common.targets()}
    patches, sources, judges_seen, runs = [], {}, set(), []

    def add(pid, target, origin, source_path, record, extraction=None, judges=None, project=None):
        code = source_path.read_text(encoding="utf-8") if source_path and source_path.is_file() else None
        base = None
        if target in targets:
            base = (common.BENCH / target / "project/tool.py").read_text(encoding="utf-8")
        row = {"id": pid, "target": target, "project": project or target, "origin": origin,
               "source_path": str(source_path.relative_to(ROOT)) if source_path and source_path.is_relative_to(ROOT) else None,
               "source_sha256": common.sha(code) if code is not None else None,
               "extraction": extraction or {"status": "OK"}, "credproof": facts(record),
               "ci": {"verdict": "PASS" if (record or {}).get("business_tests_all_passed") else "FAIL"} if record else {"verdict": "NOT_RUN"},
               "judges": judges or {}, "code": code,
               "diff": "".join(difflib.unified_diff(base.splitlines(True), code.splitlines(True), "vulnerable/tool.py", "patch/tool.py"))
               if base is not None and code is not None else None}
        patches.append(row)
        if code is not None:
            sources[pid] = source_path

    # Generation runs (AI patches) and their judges.
    anchor_judges: dict[str, dict] = {}
    for run in args.run:
        meta = json.loads((run / "run.json").read_text(encoding="utf-8"))
        runs.append({k: meta.get(k) for k in ("protocol", "started_at", "finished_at", "source_commit", "host", "models", "samples",
                                               "generation_options", "prompt_sha256")} | {"path": str(run)})
        judge_dirs = sorted((run / "judges").glob("*/judge.json")) if (run / "judges").is_dir() else []
        judge_rows = {}
        for jd in judge_dirs:
            name = json.loads(jd.read_text(encoding="utf-8"))["model"]["name"]
            judges_seen.add(name)
            for item in jd.parent.glob("*.json"):
                if item.name != "judge.json":
                    value = json.loads(item.read_text(encoding="utf-8"))
                    judge_rows.setdefault(value["item"], {})[name] = {"verdict": value["verdict"], "reasons": value["reasons"]}
        for pdir in sorted((run / "patches").iterdir()):
            target, model_slug, sample, rnd = pdir.name.split("__")
            model = json.loads((pdir / "request.json").read_text(encoding="utf-8"))["model"]
            check = json.loads((pdir / "check.json").read_text(encoding="utf-8")) if (pdir / "check.json").is_file() else None
            add(pdir.name, target, {"kind": "ai", "model": model, "sample": int(sample[1:]), "round": int(rnd[1:])},
                pdir / "patch.py", check, json.loads((pdir / "extraction.json").read_text(encoding="utf-8")),
                judge_rows.get(pdir.name))
        for target in targets:
            for kind in ("vulnerable", "reference"):
                for judge, value in judge_rows.get(f"{target}__{kind}", {}).items():
                    anchor_judges.setdefault(f"{target}__{kind}", {})[judge] = value

    # Target anchors (vulnerable originals and reference fixes) from validation.
    if args.validation:
        for record in json.loads((args.validation / "records.json").read_text(encoding="utf-8")):
            if record["label"] == "unrelated_change":
                continue
            kind = "vulnerable" if record["label"] == "vulnerable" else "reference"
            src = common.BENCH / record["target"] / ("project/tool.py" if kind == "vulnerable" else "reference_fix.py")
            add(f"{record['target']}__{kind}", record["target"], {"kind": kind}, src, record,
                judges=anchor_judges.get(f"{record['target']}__{kind}"))

    # Historical AI patches, unified recheck under the current rules.
    if args.history:
        dataset = {f"patch:{p['id']:02d}": p for p in json.loads((ROOT / "docs/report-v2/data/ai-patch-dataset.json").read_text(encoding="utf-8"))["patches"]}
        for record in json.loads((args.history / "records.json").read_text(encoding="utf-8")):
            if record["label"].startswith("patch:"):
                hist = dataset[record["label"]]
                add(f"hist-{hist['id']:02d}", record["project"], {"kind": "history", "run": hist["run"]},
                    ROOT / record["source"], record, project=record["project"])

    static = load_static(sources, args)
    for row in patches:
        row["static"] = static.get(row["id"])

    def summarise(rows):
        checked = [r for r in rows if r["credproof"]["verdict"] in ("PASS", "FAIL", "UNKNOWN")]
        unsafe = [r for r in checked if r["credproof"]["verdict"] == "FAIL"]
        good = [r for r in checked if r["credproof"]["verdict"] == "PASS"]
        out = {"patches": len(rows), "checked": len(checked),
               "credproof": {v: sum(r["credproof"]["verdict"] == v for r in checked) for v in ("PASS", "FAIL", "UNKNOWN")},
               "extraction_failed": sum(r["extraction"].get("status") not in ("OK", "SYNTAX_ERROR") for r in rows),
               "ci_green": sum(r["ci"]["verdict"] == "PASS" for r in checked),
               "ci_green_but_unsafe": sum(r["ci"]["verdict"] == "PASS" for r in unsafe),
               "violations": {k: sum(k in r["credproof"]["violations"] for r in unsafe)
                              for k in ("credential_leak", "boundary", "over_rejection", "business", "scenario")},
               "methods": {}}
        out["methods"]["ci"] = {"accepted_unsafe": out["ci_green_but_unsafe"], "rejected_good": sum(r["ci"]["verdict"] != "PASS" for r in good),
                                "unsafe": len(unsafe), "good": len(good)}
        if static:
            out["methods"]["static_credential_rules"] = {
                "accepted_unsafe": sum(not (r["static"] or {}).get("credential_alert") for r in unsafe),
                "rejected_good": sum(bool((r["static"] or {}).get("credential_alert")) for r in good),
                "unsafe": len(unsafe), "good": len(good),
                "leaks_found": sum(bool((r["static"] or {}).get("credential_alert")) for r in unsafe if "credential_leak" in r["credproof"]["violations"]),
                "leaks": sum("credential_leak" in r["credproof"]["violations"] for r in unsafe)}
        for judge in sorted(judges_seen):
            judged = [r for r in checked if judge in r["judges"]]
            out["methods"]["judge:" + judge] = {
                "accepted_unsafe": sum(r["judges"][judge]["verdict"] == "ACCEPT" for r in judged if r in unsafe),
                "rejected_good": sum(r["judges"][judge]["verdict"] != "ACCEPT" for r in judged if r in good),
                "invalid": sum(r["judges"][judge]["verdict"] == "INVALID" for r in judged),
                "unsafe": sum(r in unsafe for r in judged), "good": sum(r in good for r in judged)}
        return out

    ai = [r for r in patches if r["origin"]["kind"] == "ai"]
    history = [r for r in patches if r["origin"]["kind"] == "history"]
    anchors = [r for r in patches if r["origin"]["kind"] in ("vulnerable", "reference")]
    result = {
        "schema": "credproof.bench-results/v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source_commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "protocol": common.PROTOCOL, "runs": runs,
        "targets": [{"id": k, **{x: v[x] for x in ("title", "flaw_class", "cwe", "flaw", "business_tests_detect_flaw")}} for k, v in targets.items()],
        "judges": sorted(judges_seen),
        "summary": {"ai": summarise(ai), "history": summarise(history), "anchors": summarise(anchors),
                    "by_model": {m: summarise([r for r in ai if r["origin"]["model"] == m]) for m in sorted({r["origin"]["model"] for r in ai})},
                    "by_target": {t: summarise([r for r in ai if r["target"] == t]) for t in targets if any(r["target"] == t for r in ai)}},
        "patches": patches,
    }
    common.write_json(args.output, result)
    print(json.dumps({k: result["summary"][k] for k in ("ai", "history", "anchors")}, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
