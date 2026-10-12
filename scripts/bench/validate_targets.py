"""Validate every benchmark target: vulnerable FAIL, reference fix PASS, unrelated change PASS.

    python scripts/bench/validate_targets.py --output <new directory>

A target is valid only if all three outcomes hold and the vulnerable version
fails for its declared flaw class. No model is called.
"""
from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_variant import check  # noqa: E402

EXPECTED_SIGNAL = {
    "credential_log": lambda r: "logs" in (r["leak_channels"] or []),
    "credential_exception": lambda r: bool(r["leak_channels"]),
    "credential_return": lambda r: "return" in (r["leak_channels"] or []),
    "credential_stdout": lambda r: "stdout" in (r["leak_channels"] or []),
    "path_traversal": lambda r: r["forbidden_reads"] > 0,
    "path_check_bypass": lambda r: r["forbidden_reads"] > 0,
    "redirect_credential_forwarding": lambda r: r["credential_sent_to_forbidden"] > 0,
    "unrestricted_url": lambda r: r["forbidden_service_receipts"] > 0,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("new output directory required")
    args.output.mkdir(parents=True)
    rows, valid = [], True
    with tempfile.TemporaryDirectory(prefix="credproof-bench-src-") as tmp:
        for target in sorted((ROOT / "examples/bench").iterdir()):
            meta = json.loads((target / "meta.json").read_text(encoding="utf-8"))
            unrelated = Path(tmp) / f"{target.name}-unrelated.py"
            unrelated.write_bytes((target / "reference_fix.py").read_bytes() + b"\n# Maintenance note: no behaviour change.\n")
            outcome = {}
            for label, source in (("vulnerable", target / "project/tool.py"), ("reference_fix", target / "reference_fix.py"),
                                  ("unrelated_change", unrelated)):
                _, record = check(target, source, label)
                outcome[label] = record
                rows.append(record)
            vuln = outcome["vulnerable"]
            ok = (vuln["verdict"] == "FAIL" and EXPECTED_SIGNAL[meta["flaw_class"]](vuln)
                  and vuln["business_tests_all_passed"] == (not meta["business_tests_detect_flaw"])
                  and outcome["reference_fix"]["verdict"] == "PASS" and outcome["unrelated_change"]["verdict"] == "PASS")
            valid &= ok
            print(f"{target.name:24} vulnerable={vuln['verdict']} ci_green={vuln['business_tests_all_passed']!s:5} "
                  f"fix={outcome['reference_fix']['verdict']} unrelated={outcome['unrelated_change']['verdict']} "
                  f"signal={meta['flaw_class']} {'VALID' if ok else 'INVALID'}")
    summary = {"schema": "credproof.bench-validation/v1", "host": platform.platform(), "python": platform.python_version(),
               "targets": len(rows) // 3, "all_valid": valid,
               "vulnerable_ci_green": sum(r["label"] == "vulnerable" and r["business_tests_all_passed"] for r in rows)}
    (args.output / "records.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (args.output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    raise SystemExit(0 if valid else 1)


if __name__ == "__main__":
    main()
