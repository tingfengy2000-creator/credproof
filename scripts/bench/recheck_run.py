"""Independent re-check of a finished bench-v1 run: same frozen checker, same patch bytes, compare records.

Reads experiments/bench-v1/<run>/patches/*/patch.py, re-runs check_variant.check on this host
and compares verdict, failed checks, leak channels and business result with the recorded check.json.
No model inference. Writes <output>/records.json and <output>/summary.json.

    python scripts/bench/recheck_run.py --run experiments/bench-v1/<run-id> --output docs/bench/evidence-linux/run-recheck
"""
from __future__ import annotations

import argparse
import collections
import json
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402
from check_variant import check  # noqa: E402

FIELDS = (("verdict", "verdict"), ("failed_checks", "failed_checks"),
          ("leak_channels", "leak_channels"), ("business_tests_all_passed", "business"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    for pdir in sorted((args.run / "patches").iterdir()):
        if not (pdir / "patch.py").is_file():
            rows.append({"id": pdir.name, "skipped": "no extracted code"})
            continue
        _, mine = check(common.BENCH / pdir.name.split("__")[0], pdir / "patch.py", pdir.name)
        theirs = json.loads((pdir / "check.json").read_text(encoding="utf-8"))
        row = {"id": pdir.name}
        for key, name in FIELDS:
            a, b = mine.get(key), theirs.get(key)
            if isinstance(a, list) or isinstance(b, list):
                a, b = sorted(a or []), sorted(b or [])
            row[name + "_here"], row[name + "_recorded"] = a, b
        row["identical"] = all(row[n + "_here"] == row[n + "_recorded"] for _, n in FIELDS)
        rows.append(row)
        print(pdir.name, row["verdict_here"], row["verdict_recorded"], "same" if row["identical"] else "DIFFERENT", flush=True)
    checked = [r for r in rows if "skipped" not in r]
    summary = {"kind": "INDEPENDENT_RECHECK", "run": args.run.as_posix(), "host": platform.platform(),
               "patches": len(rows), "checked": len(checked), "identical": sum(r["identical"] for r in checked),
               "verdicts_here": dict(collections.Counter(r["verdict_here"] for r in checked))}
    common.write_json(args.output / "records.json", rows)
    common.write_json(args.output / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
