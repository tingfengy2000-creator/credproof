#!/usr/bin/env python3
"""Prospectively registered synthetic mechanism pilot; never scans user sources.

Case labels and expected answers remain outside each frozen bundle. The independent
oracle only interprets an allowlisted AST from templates generated in this module;
it never imports candidates or executes repository tests.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from typing import Any
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return sha256(path.read_bytes())


def dump(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_binary(explicit: str | None) -> str:
    found = explicit or shutil.which("git")
    if found:
        return str(Path(found).resolve())
    bundled = (Path.home() / ".cache/codex-runtimes/codex-primary-runtime/"
               "dependencies/native/git/cmd/git.exe")
    if bundled.is_file():
        return str(bundled)
    raise RuntimeError("Git not found; supply --git. No download is performed.")


def git(git_exe: str, repo: Path, *args: str) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0"})
    # Every repository passed here was created by this runner, below this run root.
    result = subprocess.run([git_exe, "-c", "core.autocrlf=false", "-C", str(repo), *args],
                            capture_output=True, check=True, timeout=20, env=env)
    return result.stdout


def template(kind: str, token: str) -> str:
    if kind == "format":
        return ("import os\n\n# Isolated demonstration configuration.\n"
                f"SERVICE_TOKEN  =  '{token}'  # offline synthetic value\n"
                "SERVICE_NAME = 'demo-service'\n\n"
                "def authorization_header():\n    return 'Bearer ' + SERVICE_TOKEN\n")
    if kind == "order":
        return ("import os\n\n"
                "def authorization_header():\n    return 'Bearer ' + SERVICE_TOKEN\n\n"
                "SERVICE_NAME = 'demo-service'\nRETRY_LIMIT = 2\n"
                f'SERVICE_TOKEN = "{token}"\n')
    return ("import os\n\nSERVICE_NAME = 'demo-service'\n"
            f'SERVICE_TOKEN = "{token}"\n\n'
            "def authorization_header():\n    return 'Bearer ' + SERVICE_TOKEN\n")


def manifest(directory: Path, scope: list[str]) -> dict[str, str | None]:
    return {name: file_hash(directory / name) if (directory / name).is_file() else None
            for name in scope}


def original_state(git_exe: str, repo: Path, scope: list[str]) -> dict[str, Any]:
    return {"worktree": manifest(repo, scope),
            "index": {name: sha256(git(git_exe, repo, "show", ":" + name)) for name in scope}}


def assignment(tree: ast.Module, symbol: str) -> ast.Assign:
    matches = [node for node in tree.body if isinstance(node, ast.Assign)
               and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
               and node.targets[0].id == symbol]
    if len(matches) != 1:
        raise ValueError("Expected exactly one module-level target assignment")
    return matches[0]


def replace_value(path: Path, symbol: str, expression: str) -> None:
    """Replace only the AST value span, preserving generated source surroundings."""
    text = path.read_text(encoding="utf-8")
    value = assignment(ast.parse(text), symbol).value
    if value.lineno != value.end_lineno:
        raise ValueError("Pilot only mutates single-line values")
    lines = text.splitlines(keepends=True)
    # Generated lines are ASCII; Python AST byte offsets equal these indices.
    line = lines[value.lineno - 1]
    lines[value.lineno - 1] = line[:value.col_offset] + expression + line[value.end_col_offset:]
    path.write_text("".join(lines), encoding="utf-8", newline="")


def safe_behavior(tree: ast.Module, environment: dict[str, str], symbol: str) -> str:
    """Small AST interpreter for our own three fixtures; no eval/exec/import."""
    names: dict[str, Any] = {}
    function: ast.FunctionDef | None = None

    def expression(node: ast.AST) -> Any:
        if isinstance(node, ast.Constant) and isinstance(node.value, (str, int, bool)):
            return node.value
        if isinstance(node, ast.Name):
            return names[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return expression(node.left) + expression(node.right)
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute)
                and isinstance(node.value.value, ast.Name) and node.value.value.id == "os"
                and node.value.attr == "environ"):
            return environment[expression(node.slice)]
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get" and isinstance(node.func.value, ast.Attribute)
                and isinstance(node.func.value.value, ast.Name)
                and node.func.value.value.id == "os" and node.func.value.attr == "environ"
                and not node.keywords and len(node.args) in (1, 2)):
            values = [expression(arg) for arg in node.args]
            return environment.get(values[0], values[1] if len(values) == 2 else None)
        raise ValueError("Outside the independent oracle's generated-fixture profile")

    for node in tree.body:
        if isinstance(node, ast.Import) and all(x.name == "os" and x.asname is None for x in node.names):
            continue
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            names[node.targets[0].id] = expression(node.value)
        elif isinstance(node, ast.FunctionDef) and node.name == "authorization_header":
            if (node.args.args or node.args.posonlyargs or node.args.kwonlyargs or node.args.vararg
                    or node.args.kwarg or node.decorator_list or len(node.body) != 1
                    or not isinstance(node.body[0], ast.Return)):
                raise ValueError("Unsupported controlled function")
            function = node
        else:
            raise ValueError("Unsupported generated module")
    if function is None or symbol not in names:
        raise ValueError("Controlled function or assignment missing")
    return expression(function.body[0].value)


def independent_facts(before: Path, candidate: Path, token: str, protocol: dict[str, Any]) -> dict[str, Any]:
    target, symbol, env_name = (protocol[k] for k in ("target", "symbol", "environment_variable"))
    text = (candidate / target).read_text(encoding="utf-8")
    facts: dict[str, Any] = {"syntax_valid": False, "required_env_read": False,
                             "positive_behavior": False, "missing_env_fails_closed": False,
                             "only_authorized_change": False}
    facts["old_value_absent"] = all(token.encode() not in (candidate / name).read_bytes()
                                    for name in protocol["scope"])
    facts["non_target_files_unchanged"] = all(
        (before / name).read_bytes() == (candidate / name).read_bytes()
        for name in protocol["scope"] if name != target)
    try:
        current, prior = ast.parse(text), ast.parse((before / target).read_text(encoding="utf-8"))
        facts["syntax_valid"] = True
        value = assignment(current, symbol).value
        facts["required_env_read"] = ast.dump(value) == ast.dump(ast.parse(f'os.environ["{env_name}"]', mode="eval").body)
        normalized_current, normalized_prior = copy.deepcopy(current), copy.deepcopy(prior)
        assignment(normalized_current, symbol).value = ast.Constant(value="ORACLE_REPLACED_VALUE")
        assignment(normalized_prior, symbol).value = ast.Constant(value="ORACLE_REPLACED_VALUE")
        facts["only_authorized_change"] = (facts["required_env_read"] and facts["non_target_files_unchanged"]
                                             and ast.dump(normalized_current) == ast.dump(normalized_prior))
        try:
            injected = "LOCAL_ORACLE_DUMMY_VALUE"
            facts["positive_behavior"] = safe_behavior(current, {env_name: injected}, symbol) == "Bearer " + injected
        except (KeyError, TypeError, ValueError):
            pass
        try:
            safe_behavior(current, {}, symbol)
        except KeyError as exc:
            facts["missing_env_fails_closed"] = exc.args == (env_name,)
        except (TypeError, ValueError):
            pass
    except (SyntaxError, ValueError):
        pass
    return facts


def oracle(case: dict[str, Any], before: Path, candidate: Path, token: str,
           protocol: dict[str, Any], delivery: dict[str, Any]) -> dict[str, Any]:
    facts = independent_facts(before, candidate, token, protocol)
    mutation = case["mutation"]
    if case["layer"] == "delivery":
        if not delivery.get("fault_constructed"):
            raise AssertionError("Independent delivery-fault construction assertion failed")
        expected = "UNKNOWN"
    elif mutation == "scope_omission":
        if not delivery.get("scope_incomplete"):
            raise AssertionError("Scope omission was not actually constructed")
        if not all(facts.values()):
            raise AssertionError("Incomplete-scope case must retain a valid candidate")
        expected = "UNKNOWN"
    elif mutation == "missing_function":
        if not delivery.get("function_missing") or not all(facts.values()):
            raise AssertionError("Missing-function case must have a valid candidate and no function evidence")
        expected = "UNKNOWN"
    else:
        expected = "PASS" if all(facts.values()) else "FAIL"
        required_facts = {
            "constant": {"syntax_valid": True, "old_value_absent": True,
                         "positive_behavior": False, "missing_env_fails_closed": False},
            "fallback": {"syntax_valid": True, "old_value_absent": False,
                         "positive_behavior": True, "missing_env_fails_closed": False},
            "syntax": {"syntax_valid": False},
            "residual": {"syntax_valid": True, "old_value_absent": False,
                         "positive_behavior": True, "non_target_files_unchanged": False},
            "unrelated": {"syntax_valid": True, "old_value_absent": True,
                          "positive_behavior": True, "non_target_files_unchanged": False},
            "wrong_environment": {"syntax_valid": True, "old_value_absent": True,
                                  "positive_behavior": False, "required_env_read": False},
        }.get(mutation, {})
        if any(facts[key] != value for key, value in required_facts.items()):
            raise AssertionError("The intended specific mutation was not constructed")
        if mutation == "index_residual" and not delivery.get("worktree_absent_index_present"):
            raise AssertionError("Index/worktree split was not independently established")
    if expected != case["expected_C"]:
        raise AssertionError(f"Constructed oracle {expected} differs from registered {case['expected_C']}")
    return {"expected_verdict": expected, "facts": facts, "delivery_facts": delivery,
            "method": "independent allowlisted AST interpretation and direct file comparisons"}


def make_object(object_root: Path, protocol: dict[str, Any], fixture: str,
                scanner: Any, git_exe: str, token: str, index_residual: bool = False) -> dict[str, Any]:
    from credproof.core import freeze

    repo, bundle = object_root / "repo", object_root / "bundle"
    repo.mkdir(parents=True, exist_ok=False)
    (repo / protocol["target"]).write_text(template(fixture, token), encoding="utf-8", newline="")
    (repo / "notes.txt").write_text("Documentation fixture. No account or network access.\n", encoding="utf-8", newline="")
    git(git_exe, repo, "init", "--quiet")
    git(git_exe, repo, "add", "--", *protocol["scope"])
    if index_residual:
        replace_value(repo / protocol["target"], protocol["symbol"],
                      f'os.environ["{protocol["environment_variable"]}"]')
    saved_original = original_state(git_exe, repo, protocol["scope"])
    contract = freeze(repo, bundle, scanner, source=protocol["source"], scope=protocol["scope"],
                      target=protocol["target"], symbol=protocol["symbol"],
                      env_name=protocol["environment_variable"], allow_fixture=True)
    return {"repo": repo, "bundle": bundle, "contract": contract,
            "original": saved_original, "token": token}


def mutate(candidate: Path, kind: str, token: str, protocol: dict[str, Any]) -> None:
    target, symbol = candidate / protocol["target"], protocol["symbol"]
    env_name = protocol["environment_variable"]
    if kind in ("constant", "stale"):
        replace_value(target, symbol, '"not-a-secret-but-wrong"')
    elif kind == "fallback":
        replace_value(target, symbol, f'os.environ.get("{env_name}", "{token}")')
    elif kind == "syntax":
        target.write_text(target.read_text(encoding="utf-8") + "\ndef broken(:\n", encoding="utf-8", newline="")
    elif kind == "residual":
        (candidate / "notes.txt").write_text("Unremoved test value: " + token + "\n", encoding="utf-8", newline="")
    elif kind == "unrelated":
        (candidate / "notes.txt").write_text("Unrelated documentation was changed.\n", encoding="utf-8", newline="")
    elif kind == "wrong_environment":
        replace_value(target, symbol, 'os.environ["UNEXPECTED_OTHER_VARIABLE"]')


def compact_report(report: dict[str, Any]) -> dict[str, Any]:
    # Retain the actual aggregate/obligations, not a reconstructed success claim.
    return copy.deepcopy(report)


def run_trial(case: dict[str, Any], repeat: int, number: int, run_dir: Path,
              protocol: dict[str, Any], scanner: Any, config: Path, exe: Path,
              git_exe: str) -> dict[str, Any]:
    from credproof.core import collect, assess
    from credproof.scanner import Gitleaks

    start = time.perf_counter()
    relative = Path("objects") / f"o{number:04d}"
    object_root = run_dir / relative
    token = protocol["synthetic_token_prefix"] + sha256(f"{run_dir.name}:{number}".encode())[:24].upper()
    row: dict[str, Any] = {"case_id": case["id"], "layer": case["layer"], "repeat": repeat,
                           "object_relative_path": relative.as_posix(), "expected_C": case["expected_C"],
                           "oracle": None, "reports": {}, "C_matches_oracle": False,
                           "original_unchanged": None, "error": None}
    obj: dict[str, Any] | None = None
    try:
        mutation = case["mutation"]
        obj = make_object(object_root, protocol, case["fixture"], scanner, git_exe, token,
                          index_residual=mutation == "index_residual")
        bundle = obj["bundle"]
        candidate = bundle / "candidate"
        delivery: dict[str, Any] = {}
        if mutation == "index_residual":
            delivery["worktree_absent_index_present"] = (
                token.encode() not in (obj["repo"] / protocol["target"]).read_bytes()
                and token.encode() in git(git_exe, obj["repo"], "show", ":" + protocol["target"]))
        if mutation == "stale":
            valid_at_collection = all(independent_facts(bundle / "before", candidate, token, protocol).values())
            evidence = collect(bundle, scanner)
            collected_manifest = manifest(candidate, protocol["scope"])
            mutate(candidate, mutation, token, protocol)
            delivery["fault_constructed"] = valid_at_collection and collected_manifest != manifest(candidate, protocol["scope"])
            delivery["collected_candidate_manifest"] = collected_manifest
            delivery["current_candidate_manifest"] = manifest(candidate, protocol["scope"])
        elif mutation == "cross_object":
            evidence = collect(bundle, scanner)
            donor_token = protocol["synthetic_token_prefix"] + sha256((token + "donor").encode())[:24].upper()
            donor = make_object(object_root / "donor", protocol, "format", scanner, git_exe, donor_token)
            donor_evidence = collect(donor["bundle"], scanner)
            evidence["checks"]["scan"] = copy.deepcopy(donor_evidence["checks"]["scan"])
            delivery["fault_constructed"] = (
                evidence["checks"]["scan"]["binding"]["contract_id"] != evidence["binding"]["contract_id"]
                and (donor["bundle"] / "before" / protocol["target"]).read_bytes()
                != (bundle / "before" / protocol["target"]).read_bytes())
            delivery["donor_original_unchanged"] = (donor["original"] == original_state(git_exe, donor["repo"], protocol["scope"]))
        elif mutation == "cross_scope":
            evidence = collect(bundle, scanner)
            narrower = collect(bundle, scanner, scope_override=[protocol["target"]])
            evidence["checks"]["scan"] = copy.deepcopy(narrower["checks"]["scan"])
            delivery["fault_constructed"] = (narrower["scope"] != protocol["scope"]
                and evidence["checks"]["scan"]["binding"]["scope_id"] != evidence["binding"]["scope_id"])
        elif mutation == "cross_rule":
            evidence = collect(bundle, scanner)
            # A real collect with a different config digest, not a fabricated status.
            other_config = object_root / "donor-config.toml"
            other_config.write_bytes(config.read_bytes() + b"\n# Controlled alternate configuration identity.\n")
            other_scanner = Gitleaks(exe, other_config)
            alternative = collect(bundle, other_scanner)
            evidence["checks"]["scan"] = copy.deepcopy(alternative["checks"]["scan"])
            delivery["fault_constructed"] = (
                file_hash(other_config) != file_hash(config)
                and evidence["checks"]["scan"]["binding"]["rules_id"] != evidence["binding"]["rules_id"])
        else:
            mutate(candidate, mutation, token, protocol)
            if mutation == "scope_omission":
                evidence = collect(bundle, scanner, scope_override=[protocol["target"]])
                delivery["scope_incomplete"] = evidence["scope"] != protocol["scope"]
            elif mutation == "missing_function":
                evidence = collect(bundle, scanner, skip=("function",))
                delivery["function_missing"] = "function" not in evidence["checks"]
            else:
                evidence = collect(bundle, scanner)

        row["oracle"] = oracle(case, bundle / "before", candidate, token, protocol, delivery)
        row["evidence_summary"] = {"binding": evidence.get("binding"), "scope": evidence.get("scope"),
                                   "checks": {k: {"status": v.get("status"), "binding": v.get("binding"),
                                                   "duration_ms": v.get("duration_ms")}
                                              for k, v in evidence.get("checks", {}).items()},
                                   "shared_full_collect_ms": evidence.get("duration_ms")}
        for mode in protocol["modes"]:
            row["reports"][mode] = compact_report(assess(bundle, copy.deepcopy(evidence), scanner, mode=mode))
        remaining = row["reports"]["C"].get("remaining_risks", {})
        expected_worktree = "ABSENT_WITHIN_SCOPE" if mutation == "index_residual" else "PRESENT"
        row["remaining_risks_match_oracle"] = (
            remaining.get("index", {}).get("presence") == "PRESENT"
            and remaining.get("worktree", {}).get("presence") == expected_worktree
            and remaining.get("history") == "NOT_SCANNED"
            and remaining.get("external_revocation") == "UNKNOWN")
        if not row["remaining_risks_match_oracle"]:
            raise AssertionError("Reported source/history/cloud states differ from the independently generated fixture facts")
        # This is a reasonable recollection comparator, not old evidence with a new name.
        fresh_start = time.perf_counter()
        fresh_evidence = collect(bundle, scanner, skip=("removal", "allowed_changes"))
        row["reports"]["B-fresh"] = compact_report(assess(bundle, fresh_evidence, scanner, mode="B"))
        facts = row["oracle"]["facts"]
        row["B_fresh_expected"] = "PASS" if all(facts[key] for key in (
            "old_value_absent", "syntax_valid", "positive_behavior", "missing_env_fails_closed")) else "FAIL"
        row["B_fresh_matches_own_oracle"] = row["reports"]["B-fresh"]["verdict"] == row["B_fresh_expected"]
        row["B_fresh_total_ms"] = round((time.perf_counter() - fresh_start) * 1000, 3)
        row["C_matches_oracle"] = row["reports"]["C"]["verdict"] == row["oracle"]["expected_verdict"]
        row["original_unchanged"] = obj["original"] == original_state(git_exe, obj["repo"], protocol["scope"])
        if not row["original_unchanged"] or delivery.get("donor_original_unchanged") is False:
            raise AssertionError("An original generated repository changed during the trial")
    except Exception as exc:
        # Do not include candidate contents, token, or arbitrary subprocess stdout.
        row["error"] = {"type": type(exc).__name__, "message": str(exc).replace(token, "<synthetic-redacted>"),
                        "traceback_locations": [{"file": Path(frame.filename).name, "line": frame.lineno,
                                                  "function": frame.name}
                                                 for frame in traceback.extract_tb(exc.__traceback__)]}
        if obj is not None:
            try:
                row["original_unchanged"] = obj["original"] == original_state(git_exe, obj["repo"], protocol["scope"])
            except Exception:
                row["original_unchanged"] = False
    row["elapsed_seconds"] = round(time.perf_counter() - start, 6)
    return row


def summarize(trials: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"case_count": len(protocol["cases"]), "trial_count": len(trials),
                              "errors": sum(t["error"] is not None for t in trials),
                              "C_oracle_disagreements": sum(not t["C_matches_oracle"] for t in trials if t["error"] is None),
                              "B_fresh_oracle_disagreements": sum(not t["B_fresh_matches_own_oracle"] for t in trials if t["error"] is None),
                              "original_change_incidents": sum(t["original_unchanged"] is False for t in trials),
                              "layers": {}, "unstable_cases": []}
    modes = protocol["modes"]
    for layer in protocol["layers"]:
        rows = [t for t in trials if t["layer"] == layer and t["error"] is None]
        summary["layers"][layer] = {"completed_trials": len(rows), "by_mode": {}}
        for mode in modes:
            stats = {}
            for expected in ("PASS", "FAIL", "UNKNOWN"):
                group = [t for t in rows if t["expected_C"] == expected]
                stats["expected_" + expected] = {"trials": len(group),
                    "observed": {v: sum(t["reports"][mode]["verdict"] == v for t in group)
                                 for v in ("PASS", "FAIL", "UNKNOWN")}}
            summary["layers"][layer]["by_mode"][mode] = stats
        summary["layers"][layer]["B_fresh_control"] = {
            "trials": len(rows),
            "matches_recollected_scope_oracle": sum(t["B_fresh_matches_own_oracle"] for t in rows),
            "observed": {v: sum(t["reports"]["B-fresh"]["verdict"] == v for t in rows)
                         for v in ("PASS", "FAIL", "UNKNOWN")},
            "note": "newly collected evidence; not scored as erroneous PASS against delivered-evidence UNKNOWN"}
    summary["case_level_metrics"] = {}
    groups = {label: [case["id"] for case in protocol["cases"] if case["expected_C"] == label]
              for label in ("PASS", "FAIL", "UNKNOWN")}
    for mode in modes:
        def observations(case_id: str) -> list[str]:
            return ["ERROR" if t["error"] else t["reports"][mode]["verdict"]
                    for t in trials if t["case_id"] == case_id]
        def metric(ids: list[str], predicate: Any) -> dict[str, int]:
            return {"numerator": sum(predicate(observations(case_id)) for case_id in ids),
                    "denominator": len(ids)}
        ids = [case["id"] for case in protocol["cases"]]
        summary["case_level_metrics"][mode] = {
            "bad_patch_false_accept": metric(groups["FAIL"], lambda values: "PASS" in values),
            "valid_accept": metric(groups["PASS"], lambda values: bool(values) and all(v == "PASS" for v in values)),
            "insufficient_evidence_false_accept": metric(groups["UNKNOWN"], lambda values: "PASS" in values),
            "overall_stable_UNKNOWN": metric(ids, lambda values: bool(values) and all(v == "UNKNOWN" for v in values)),
            "mixed_outcomes": metric(ids, lambda values: len(set(values)) > 1),
            "repeat_rule": "false acceptance uses any repeat; valid acceptance and stable UNKNOWN require all repeats; errors/mixed outcomes are retained"}
    for case in protocol["cases"]:
        rows = [t for t in trials if t["case_id"] == case["id"]]
        signatures = {json.dumps({"error": t["error"] and t["error"]["type"],
                                  "verdicts": {m: t["reports"].get(m, {}).get("verdict") for m in modes + ["B-fresh"]}}, sort_keys=True)
                      for t in rows}
        if len(signatures) > 1:
            summary["unstable_cases"].append(case["id"])
    return summary


def measure_overhead(bundle: Path, scanner: Any) -> dict[str, Any]:
    """Nine fresh collections; never infer mode cost from shared full collection."""
    from credproof.core import collect, assess

    skip = {"A": ("syntax", "function", "removal", "allowed_changes"),
            "B": ("removal", "allowed_changes"), "C": ()}
    rows = []
    # Rotate the run order to reduce a simple fixed-order cache bias.
    for order in (("A", "B", "C"), ("B", "C", "A"), ("C", "A", "B")):
        for mode in order:
            start = time.perf_counter()
            evidence = collect(bundle, scanner, skip=skip[mode])
            report = assess(bundle, evidence, scanner, mode=mode)
            rows.append({"mode": mode, "elapsed_ms": (time.perf_counter() - start) * 1000,
                         "collect_ms": evidence.get("duration_ms"),
                         "assess_ms": report.get("duration_ms"), "verdict": report["verdict"]})
    grouped = {}
    for mode in skip:
        values = [row["elapsed_ms"] for row in rows if row["mode"] == mode]
        grouped[mode] = {"n": len(values), "mean_ms": statistics.mean(values),
                         "sample_variance_ms2": statistics.variance(values),
                         "min_ms": min(values), "max_ms": max(values)}
    return {"fixture": "good_basic", "fresh_independent_collection": True, "samples": rows,
            "by_mode": grouped, "C_minus_B_mean_ms": grouped["C"]["mean_ms"] - grouped["B"]["mean_ms"],
            "all_correct": all(row["verdict"] == "PASS" for row in rows),
            "interpretation": "single two-file fixture, 3 samples per mode; descriptive local overhead, not general speed advantage"}


def markdown(result: dict[str, Any], protocol: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = ["# CredProof synthetic mechanism pilot", "",
             "All 16 cases were visible during development; there is no independent final holdout. "
             "These are locally generated fixtures, not a real-world detection benchmark. "
             "A/B are constructed comparators, not claims about product defaults.", "",
             f"Protocol SHA-256: `{result['protocol_sha256']}`  ",
             f"Gitleaks: `{result['gitleaks_version']}`  ",
             f"Cases: {summary['case_count']}; repeated trials: {summary['trial_count']}; "
             f"errors: {summary['errors']}; C/oracle disagreements: {summary['C_oracle_disagreements']}.", "",
             f"Frozen inputs unchanged throughout run: {result.get('frozen_inputs_unchanged')}; "
             f"B-fresh/new-input oracle disagreements: {summary['B_fresh_oracle_disagreements']}.", "",
             "Repeats test stability; they do not increase the number of independent case families. "
             "UNKNOWN cases represent missing/misbound evidence and are separate from bad patches.", ""]
    modes = protocol["modes"] + ["B-fresh"]
    lines += ["## Case-level counts", "",
              "False acceptance counts a case if any repeat passes. Valid acceptance and stable UNKNOWN require every repeat. "
              "Mixed/error outcomes remain visible; repeats do not increase these denominators.", "",
              "| Mode | Bad-patch false acceptance | Valid acceptance | Insufficient/misbound evidence false acceptance | Overall stable UNKNOWN | Mixed cases |",
              "|---|---|---|---|---|---|"]
    for mode, metrics in summary["case_level_metrics"].items():
        cells = [f"{metrics[key]['numerator']}/{metrics[key]['denominator']}" for key in (
            "bad_patch_false_accept", "valid_accept", "insufficient_evidence_false_accept", "overall_stable_UNKNOWN", "mixed_outcomes")]
        lines.append("| " + " | ".join([mode, *cells]) + " |")
    lines += ["", "Fresh has ten complete, same-scope cases. The six evidence-completeness/delivery cases exercise "
              "simplified supplied-evidence aggregation; they are not claims about a reasonable CI pipeline that reruns its fixed scope.", ""]
    for layer in protocol["layers"]:
        lines += ["## " + layer, "", "| Case | Expected C | A | B | C | C-no-binding | B-fresh | Oracle / originals |",
                  "|---|---|---|---|---|---|---|---|"]
        for case in protocol["cases"]:
            if case["layer"] != layer:
                continue
            rows = [t for t in result["trials"] if t["case_id"] == case["id"]]
            cells = []
            for mode in modes:
                values = ["ERROR" if r["error"] else r["reports"].get(mode, {}).get("verdict", "MISSING") for r in rows]
                cells.append(values[0] if len(set(values)) == 1 else "/".join(values))
            quality = ("OK" if all(not r["error"] and r["C_matches_oracle"] and r["original_unchanged"] for r in rows)
                       else "REVIEW REQUIRED")
            lines.append("| " + " | ".join([case["id"], case["expected_C"], *cells, quality]) + " |")
        lines.append("")
    timing = result.get("overhead")
    if timing and "by_mode" in timing:
        lines += ["## Independent fresh overhead samples", "",
                  "One valid two-file fixture; each mode independently recollects only its required checks. "
                  "Order rotates. These descriptive local samples do not establish a speed advantage.", "",
                  "| Mode | N | Mean ms | Min ms | Max ms | Sample variance ms² |",
                  "|---|---|---|---|---|---|"]
        for mode, values in timing["by_mode"].items():
            lines.append(f"| {mode} | {values['n']} | {values['mean_ms']:.3f} | {values['min_ms']:.3f} | "
                         f"{values['max_ms']:.3f} | {values['sample_variance_ms2']:.3f} |")
        lines += ["", f"Observed mean C − B: {timing['C_minus_B_mean_ms']:.3f} ms; "
                  f"all timing checks passed: {timing['all_correct']}.", ""]
    elif timing:
        lines += ["## Timing error", "", str(timing.get("error")), ""]
    lines += ["## Interpretation limits", "",
              "- The index-residual case is a valid local-copy PASS with unchanged original risk, not a rejected bad fix.",
              "- B-fresh recollects current candidate evidence for scan/syntax/function on the full intended scope. "
              "It is judged against its new-input oracle, not the old delivered-evidence UNKNOWN label. "
              "Read this column before attributing delivery-fault benefits uniquely to binding checks.",
              "- Shared full-collection timings and assess timings are recorded separately. No per-mode execution-speed ranking is claimed.",
              "- No precision/recall, cloud-validity, SOTA, or population confidence-interval claim follows from this pilot.",
              "- JSON retains all trial errors, exact verdicts, obligation reports and independent oracle facts.", "",
              "Unstable cases: " + (", ".join(summary["unstable_cases"]) or "none observed"), ""]
    errors = [t for t in result["trials"] if t["error"]]
    if errors:
        lines += ["## Errors retained", ""]
        for row in errors:
            message = row["error"]["message"].replace("\n", " ").replace("|", "/")
            lines.append(f"- {row['case_id']} repeat {row['repeat']}: {row['error']['type']}: {message}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gitleaks", required=True, type=Path)
    parser.add_argument("--config", type=Path, default=ROOT / "config/synthetic-gitleaks.toml")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/pilot")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--git", help="Optional path to Git executable")
    args = parser.parse_args()
    if not 1 <= args.repeats <= 10:
        parser.error("--repeats must be between 1 and 10 (stability repetitions, not extra case families)")
    exe, config = args.gitleaks.resolve(), args.config.resolve()
    if not exe.is_file() or not config.is_file():
        parser.error("A local Gitleaks executable and local frozen configuration are required")
    git_exe = git_binary(args.git)
    # The core invokes Git by name. Add only the resolved executable directory for
    # this process and its children; this does not persistently modify system PATH.
    os.environ["PATH"] = str(Path(git_exe).parent) + os.pathsep + os.environ.get("PATH", "")
    protocol_path = Path(__file__).with_name("protocol.json")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:8]
    run_dir = args.output.resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    version = subprocess.run([str(exe), "version"], capture_output=True, text=True, check=True, timeout=15).stdout.strip()
    try:
        head = git(git_exe, ROOT, "rev-parse", "HEAD").decode().strip()
    except subprocess.SubprocessError:
        head = None
    from credproof.scanner import Gitleaks
    scanner = Gitleaks(exe, config)
    code_paths = [Path(__file__), ROOT / "credproof/core.py", ROOT / "credproof/scanner.py",
                  ROOT / "credproof/__init__.py"]
    source_hashes = {p.relative_to(ROOT).as_posix(): file_hash(p) for p in code_paths}
    result: dict[str, Any] = {"protocol_id": protocol["protocol_id"], "protocol_sha256": file_hash(protocol_path),
                             "runner_sha256": file_hash(Path(__file__)), "git_head": head,
                             "python_version": platform.python_version(), "gitleaks_version": version,
                             "gitleaks_exe_sha256": file_hash(exe), "config_sha256": file_hash(config),
                             "source_sha256": source_hashes,
                             "started_at": utc_now(), "completed_at": None, "repeats": args.repeats,
                             "parameters": {"scope": protocol["scope"], "source": protocol["source"],
                                            "modes": protocol["modes"], "B_fresh": True},
                             "trials": [], "summary": None}
    dump(run_dir / "protocol-frozen.json", protocol)
    dump(run_dir / "run-metadata.json", result)
    number = 0
    for repeat in range(1, args.repeats + 1):
        for case in protocol["cases"]:
            number += 1
            trial = run_trial(case, repeat, number, run_dir, protocol, scanner, config, exe, git_exe)
            result["trials"].append(trial)
            dump(run_dir / "results.partial.json", result)
            print(f"[{number}/{len(protocol['cases']) * args.repeats}] {case['id']}: "
                  f"{'ERROR' if trial['error'] else trial['reports']['C']['verdict']}", flush=True)
    try:
        result["overhead"] = measure_overhead(run_dir / "objects/o0001/bundle", scanner)
    except Exception as exc:
        result["overhead"] = {"error": type(exc).__name__ + ": " + str(exc), "all_correct": False}
    result["completed_at"] = utc_now()
    result["frozen_inputs_unchanged"] = (
        source_hashes == {p.relative_to(ROOT).as_posix(): file_hash(p) for p in code_paths}
        and result["protocol_sha256"] == file_hash(protocol_path)
        and result["config_sha256"] == file_hash(config)
        and result["gitleaks_exe_sha256"] == file_hash(exe))
    result["summary"] = summarize(result["trials"], protocol)
    dump(run_dir / "results.json", result)
    (run_dir / "summary.md").write_text(markdown(result, protocol), encoding="utf-8")
    print(f"Results: {run_dir / 'results.json'}", flush=True)
    summary = result["summary"]
    return 1 if (summary["errors"] or summary["C_oracle_disagreements"] or summary["B_fresh_oracle_disagreements"] or summary["original_change_incidents"]
                 or summary["unstable_cases"] or not result["overhead"].get("all_correct")
                 or not result["frozen_inputs_unchanged"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
