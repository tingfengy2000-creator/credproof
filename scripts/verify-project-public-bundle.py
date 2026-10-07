#!/usr/bin/env python3
"""Verify a public project bundle against the fixed Git blob bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--commit", required=True)
    ap.add_argument("--source-prefix", required=True)
    ap.add_argument("--bundle", type=Path, required=True)
    ap.add_argument("--receipt", type=Path, required=True)
    args = ap.parse_args()
    repo = args.repo.resolve()
    bundle = args.bundle.resolve(strict=True)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    rows = []
    for rel, expected in sorted(manifest["files"].items()):
        path = bundle / Path(rel)
        actual = sha(path.read_bytes())
        source = subprocess.check_output(
            ["git", "-C", str(repo), "show", f"{args.commit}:{args.source_prefix}/{rel}"],
            stderr=subprocess.STDOUT,
        ) if rel not in {"publication.json", "report.json"} else None
        rows.append({
            "path": rel,
            "manifest_sha256": expected,
            "actual_sha256": actual,
            "manifest_match": actual == expected,
            "git_blob_sha256": sha(source) if source is not None else None,
            "git_blob_match": source is None or sha(source) == actual,
            "bytes": len(path.read_bytes()),
            "crlf_pairs": path.read_bytes().count(b"\r\n"),
        })
    receipt = {
        "schema": "credproof.project-public-bundle-byte-verification/v1",
        "bundle": bundle.name,
        "source_commit": args.commit,
        "source_prefix": args.source_prefix,
        "rows": rows,
        "all_manifest_bytes_match": all(row["manifest_match"] for row in rows),
        "source_material_count": sum(row["git_blob_sha256"] is not None for row in rows),
        "derived_receipt_count": sum(row["git_blob_sha256"] is None for row in rows),
        "all_git_source_material_bytes_match": all(row["git_blob_match"] for row in rows if row["git_blob_sha256"] is not None),
        "all_git_source_bytes_match": all(row["git_blob_match"] for row in rows),
        "entry_path": "project/tool.py",
        "entry_sha256": next(row["actual_sha256"] for row in rows if row["path"] == "project/tool.py"),
        "entry_bytes": next(row["bytes"] for row in rows if row["path"] == "project/tool.py"),
        "entry_crlf_pairs": next(row["crlf_pairs"] for row in rows if row["path"] == "project/tool.py"),
        "note": "publication/report are derived receipts and are checked against the bundle manifest; source materials are read as Git blobs and derived receipt paths are listed separately.",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: receipt[k] for k in ("all_manifest_bytes_match", "all_git_source_bytes_match", "entry_sha256", "entry_bytes", "entry_crlf_pairs")}, indent=2))
    return 0 if receipt["all_manifest_bytes_match"] and receipt["all_git_source_bytes_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
