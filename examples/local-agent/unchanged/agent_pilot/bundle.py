"""Portable, standard-library-only export and fresh isolated recheck.

The operator must trust this tool and its judge/isolation sources. Hashes detect
changes; they are not signatures or a defense against a replaced verifier.
Candidate source is never imported or executed in the host Python interpreter.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import secrets
import sys

from . import judge
from .isolation import run_isolated

PACKAGE = Path(__file__).resolve().parent
SCHEMA = "credproof.portable-bundle.v1"
RUNTIME_FILES = ("__init__.py", "bundle.py", "judge.py", "isolation.py", "sandbox_runner.py")
EXECUTION_SECRET = re.compile(r"CP_EXEC_[A-Za-z0-9]{16,}")
TOP_RECORD = re.compile(r"(?:initial-evidence|final-validation|fixed-transform|"
                        r"verify-\d+-validation|candidate-\d+-proposal)\.json\Z")
MODEL_RECORD = re.compile(r"(?:result\.json|events\.jsonl|model-\d+-"
                          r"(?:request|response|input-budget)\.json)\Z")
MAX_RECORD_BYTES = 16 * 1024 * 1024


def _now():
    return datetime.now(timezone.utc).isoformat()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _read(path, limit=MAX_RECORD_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise ValueError("required_regular_file_unavailable_or_too_large")
    return path.read_bytes()


def _json(path):
    return json.loads(_read(path).decode("utf-8"))


def _write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")


def _text(data):
    # Match reliability.rules_hash(), which reads Python/Markdown in text mode.
    return data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")


def _rules_hash(requirements, judge_source, policy):
    return _sha((_text(requirements) + _text(judge_source) + _canonical(policy)).encode("utf-8"))


def _trusted_policy():
    # Parse trusted project source without importing its Qwen-dependent module.
    tree = ast.parse(_read(PACKAGE / "reliability.py").decode("utf-8"))
    values = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "POLICY" for t in n.targets)]
    if len(values) != 1 or not isinstance(values[0], dict):
        raise ValueError("trusted_policy_unavailable")
    return values[0]


def _public(value):
    """Reject recognizable private envelopes; redact synthetic values in records."""
    if isinstance(value, dict):
        if "auth_calls" in value or value.get("schema") == judge.SCHEMA:
            raise ValueError("private_trial_is_not_exportable")
        if "credential" in value and value["credential"] != "[REDACTED]":
            raise ValueError("raw_credential_field_is_not_exportable")
        return {_public(k): _public(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_public(v) for v in value]
    if isinstance(value, str):
        return EXECUTION_SECRET.sub("[REDACTED]", value)
    return value


README = """# Portable CredProof recheck bundle

From this directory, using ordinary Python 3.10+ (no Qwen dependencies):

    python -m agent_pilot.bundle recheck --bundle . --output recheck-01.json

The output path must be new. Candidate source is `current.py`; the original is
`original.py`. To inspect a changed candidate, edit only `current.py`, then use
a different output filename. The historical report becomes inapplicable after
an object change, but a fresh verdict can still be PASS, FAIL, or UNKNOWN.

This package contains the verifier source and fixed 13-test judge. It does not
contain model weights, .env files, raw private executions, or an inference server.
It requires the already prepared/probed isolation runtime: on Windows, WSL
Ubuntu-24.04, user tingfeng; Linux profile at
`/home/tingfeng/credproof-agent-runtime/isolation`. No original checkout is used.
The runner verifies its probe receipt and runtime hashes; missing or changed
isolation produces UNKNOWN, never a host execution fallback. Recheck does not
download, install, start a model, or silently prepare/re-probe the environment.

The fixed judge checks runtime synthetic credential leakage and the constrained
tool response/authentication contract. It is not a general vulnerability proof,
nor evidence that an Agent diagnosed correctly or completed its whole task.
Current fresh validation cannot overwrite the historical task status.

The operator and bundled verifier/judge/isolation source must be trusted. Hashes
detect changes against the supplied manifest, but are not authentication. A party
that replaces both the verifier and its manifest can forge this package. Review
or independently pin the verifier source before executing a received bundle.
Do not treat arbitrary third-party bundles as trusted programs.

Configuration and requirements are archived explanatory material, not authority
to edit the judge or shrink its fixed matrix. Raw synthetic credentials exist
only in memory during recheck; output contains verdicts and reason codes only.
Published trace is a sanitized copy; do not assume this export is a general
real-secret discovery service. Only reviewed synthetic reliability runs apply.

CLI exit codes: 0 exported/fresh PASS, 1 fresh FAIL, 2 fresh UNKNOWN/blocked,
3 invalid arguments, input, or output path. Existing files are never overwritten.
"""


def export_bundle(run_path, out_path) -> dict:
    """Export one reliability method directory; no inference or execution."""
    run = Path(run_path).resolve(strict=True)
    output = Path(out_path).resolve()
    if not run.is_dir() or output.exists() or output == run or run in output.parents:
        raise ValueError("new_output_outside_run_required")
    original = _read(run / "original.py", 65536)
    current = _read(run / "final-candidate.py", 65536)
    if EXECUTION_SECRET.search(original.decode("utf-8")) or EXECUTION_SECRET.search(current.decode("utf-8")):
        raise ValueError("execution_credential_in_source")
    report = _json(run / "result.json")
    if not isinstance(report, dict) or not isinstance(report.get("final_validation"), dict):
        raise ValueError("reliability_report_required")
    policy = _trusted_policy()
    requirements = _read(PACKAGE / "fixtures" / "requirements.md")
    runtime = {name: _read(PACKAGE / name) for name in RUNTIME_FILES}
    rules = _rules_hash(requirements, runtime["judge.py"], policy)
    if (report.get("source_sha256") != _sha(original)
            or report.get("candidate_sha256") != _sha(current)
            or report.get("rules_sha256") != rules):
        raise ValueError("run_object_or_rules_binding_mismatch")
    # Validate/sanitize all exported data before creating any output directory.
    public_report = _public(report)
    records = {}
    for path in sorted(run.iterdir()):
        if TOP_RECORD.fullmatch(path.name):
            records["trace/" + path.name] = _public(_json(path))
    model = run / "model"
    if model.exists():
        if model.is_symlink() or not model.is_dir():
            raise ValueError("linked_model_directory_not_exportable")
        for path in sorted(model.iterdir()):
            if MODEL_RECORD.fullmatch(path.name):
                data = _read(path).decode("utf-8")
                records["trace/model/" + path.name] = (
                    [_public(json.loads(line)) for line in data.splitlines() if line.strip()]
                    if path.suffix == ".jsonl" else _public(json.loads(data)))
    configuration = {"schema": SCHEMA, "policy": policy, "required_trials": len(judge.hidden_matrix()),
                     "timeout_seconds": 10, "rule_hash_algorithm": "sha256(requirements_text+judge_text+canonical_policy)"}
    output.mkdir(parents=True, exist_ok=False)
    (output / "agent_pilot").mkdir()
    for name, data in runtime.items():
        (output / "agent_pilot" / name).write_bytes(data)
    (output / "original.py").write_bytes(original)
    (output / "current.py").write_bytes(current)
    (output / "requirements.md").write_bytes(requirements)
    (output / "README.md").write_text(README, encoding="utf-8", newline="\n")
    _write_json(output / "configuration.json", configuration)
    _write_json(output / "report.json", public_report)
    for relative, value in records.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.suffix == ".jsonl":
            with path.open("x", encoding="utf-8", newline="\n") as stream:
                stream.writelines(_canonical(row) + "\n" for row in value)
        else:
            _write_json(path, value)
    hashes = {p.relative_to(output).as_posix(): _sha(p.read_bytes())
              for p in sorted(output.rglob("*")) if p.is_file()}
    manifest = {"schema": SCHEMA, "exported_at": _now(), "hashes": hashes,
                "source_sha256": _sha(original), "candidate_sha256": _sha(current),
                "rules_sha256": rules, "trust": "trusted verifier and operator; hashes are not signatures",
                "execution_performed": False}
    _write_json(output / "manifest.json", manifest)
    return {"status": "EXPORTED", "bundle_path": str(output), "candidate_sha256": _sha(current),
            "rules_sha256": rules, "files": len(hashes) + 1, "execution_performed": False}


def _fresh(source):
    source_check = judge.validate_source(source)
    checks = [{"name": "source_profile", **source_check}]
    if source_check["verdict"] != "PASS":
        return {**source_check, "checks": checks, "checks_run": 0, "required_trials": len(judge.hidden_matrix())}
    trials, problems = [], []
    matrix = judge.hidden_matrix()  # Never selected from report/configuration.
    for number, trigger in enumerate(matrix, 1):
        credential = "CP_EXEC_" + secrets.token_hex(24)
        problem_code = "ISOLATION_CALL_UNAVAILABLE"
        try:
            result = run_isolated(source, judge.trusted_harness_source(),
                                  {**trigger, "credential": credential}, timeout_seconds=10)
            status = result.get("status")
            if status != "OK" or result.get("returncode") != 0:
                problem_code = "ISOLATED_EXECUTION_" + (status if status in {
                    "TIMEOUT", "OUTPUT_LIMIT", "PROCESS_ERROR", "ISOLATION_ERROR"} else "UNAVAILABLE")
                raise ValueError("ISOLATED_EXECUTION_UNAVAILABLE")
            problem_code = "INVALID_ISOLATED_TRANSCRIPT"
            envelope = json.loads(result["stdout"])
            trial = envelope["trial"]
            if (envelope.get("schema") != judge.SCHEMA or trial.get("credential") != credential
                    or trial.get("request") != trigger["request"] or trial.get("auth_mode") != trigger["auth_mode"]):
                raise ValueError("INVALID_ISOLATED_TRANSCRIPT")
            decision = judge.judge_trial(trial)
            trials.append(trial)
            checks.append({"name": "trial_%02d" % number, **decision,
                           "isolation_status": "OK", "duration_ms": result.get("duration_ms"),
                           "isolation_receipt": result.get("isolation_receipt")})
        except Exception:
            # Never persist/echo raw stdout, exception strings, input or credential.
            problems.append(problem_code)
            checks.append({"name": "trial_%02d" % number, "verdict": "UNKNOWN", "reasons": [problem_code]})
    verdict = judge.judge_suite(trials, source)
    verdict["reasons"] = sorted(set(verdict["reasons"]) | set(problems))
    return {**verdict, "checks": checks, "completed_trials": len(trials), "required_trials": len(matrix)}


def recheck_bundle(bundle_path, output_path) -> dict:
    """Read current objects, check old applicability, then execute the fixed judge."""
    root = Path(bundle_path).resolve(strict=True)
    output = Path(output_path).resolve()
    if output.exists() or not output.parent.is_dir():
        raise ValueError("new_output_file_in_existing_directory_required")
    checked_at = _now()
    candidate = None
    prior_reasons, block_reasons = [], []
    try:
        manifest = _json(root / "manifest.json")
        if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                or not isinstance(manifest.get("hashes"), dict)):
            raise ValueError("invalid_manifest")
        hashes = manifest["hashes"]
        report = _json(root / "report.json")
        current = _read(root / "current.py", 65536)
        candidate = _sha(current)
        original = _read(root / "original.py", 65536)
        requirements = _read(root / "requirements.md")
        configuration = _json(root / "configuration.json")
        if (not isinstance(report, dict) or not isinstance(configuration, dict)
                or configuration.get("schema") != SCHEMA or not isinstance(configuration.get("policy"), dict)):
            raise ValueError("invalid_report_or_configuration")
        # Only the fixed, loaded verifier executes. Packaged code is never dynamically imported.
        trusted = ["requirements.md", "configuration.json"] + ["agent_pilot/" + n for n in RUNTIME_FILES]
        for name in trusted:
            actual = _sha(_read(root / name))
            if hashes.get(name) != actual:
                block_reasons.append("TRUSTED_MATERIAL_CHANGED")
            if name.startswith("agent_pilot/") and _sha(_read(PACKAGE / Path(name).name)) != actual:
                block_reasons.append("LOADED_VERIFIER_DIFFERS_FROM_BUNDLE")
        rules = _rules_hash(requirements, _read(PACKAGE / "judge.py"), configuration["policy"])
        if rules != manifest.get("rules_sha256"):
            block_reasons.append("RULES_BINDING_MISMATCH")
        if candidate != report.get("candidate_sha256") or candidate != manifest.get("candidate_sha256"):
            prior_reasons.append("CANDIDATE_CHANGED")
        if _sha(original) != report.get("source_sha256") or _sha(original) != manifest.get("source_sha256"):
            prior_reasons.append("ORIGINAL_CHANGED")
        if rules != report.get("rules_sha256"):
            prior_reasons.append("REPORT_RULES_MISMATCH")
        if hashes.get("report.json") != _sha(_read(root / "report.json")):
            prior_reasons.append("REPORT_CHANGED")
        if not isinstance(report.get("final_validation"), dict):
            prior_reasons.append("REPORT_VALIDATION_MISSING")
        prior_reasons.extend(block_reasons)
        prior = not prior_reasons
        if block_reasons:
            validation = {"verdict": "UNKNOWN", "reasons": sorted(set(block_reasons)), "checks": []}
        else:
            # Keep byte hashes for object identity; the interpreter receives normalized source text.
            start_hashes = {name: _sha(_read(root / name)) for name in trusted}
            loaded_hashes = {name: _sha(_read(PACKAGE / name)) for name in RUNTIME_FILES}
            archived_hashes = {name: _sha(_read(root / name)) for name in ("report.json", "original.py", "manifest.json")}
            validation = _fresh(_text(current))
            if (candidate != _sha(_read(root / "current.py", 65536))
                    or any(value != _sha(_read(root / name)) for name, value in start_hashes.items())
                    or any(value != _sha(_read(PACKAGE / name)) for name, value in loaded_hashes.items())):
                prior = False
                prior_reasons.append("MATERIAL_CHANGED_DURING_RECHECK")
                validation = {"verdict": "UNKNOWN", "reasons": ["MATERIAL_CHANGED_DURING_RECHECK"],
                              "checks": validation["checks"]}
            elif any(value != _sha(_read(root / name)) for name, value in archived_hashes.items()):
                prior = False
                prior_reasons.append("ARCHIVE_CHANGED_DURING_RECHECK")
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        prior = False
        prior_reasons.append("BUNDLE_MATERIAL_UNAVAILABLE")
        validation = {"verdict": "UNKNOWN", "reasons": ["BUNDLE_MATERIAL_UNAVAILABLE"], "checks": []}
    result = {"status": "RECHECKED" if validation["checks"] else "BLOCKED", "checked_at": checked_at,
              "validation": validation, "candidate_sha256": candidate,
              "prior_report_applicable": prior, "prior_report_reasons": sorted(set(prior_reasons)),
              "historical_task_status_rewritten": False,
              "trust_boundary": "trusted verifier/operator; hashes detect changes, not authenticity"}
    _write_json(output, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export")
    export.add_argument("--run", required=True, type=Path)
    export.add_argument("--output", required=True, type=Path)
    recheck = commands.add_parser("recheck")
    recheck.add_argument("--bundle", required=True, type=Path)
    recheck.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = (export_bundle(args.run, args.output) if args.command == "export"
                  else recheck_bundle(args.bundle, args.output))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if args.command == "export" else {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["validation"]["verdict"]]
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        print(json.dumps({"status": "ERROR", "reason": "invalid_or_unavailable_input_or_output"}))
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
