"""Build a public, byte-reproducible project bundle from a fixed Git tree.

This does not rerun a model.  It reads Git blobs so the published newline
bytes are explicit and cannot depend on core.autocrlf or the checkout mode.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess


FILES = (
    "candidate.py",
    "configuration.json",
    "original.py",
    "project/README.md",
    "project/credproof.toml",
    "project/tests/test_business.py",
    "project/tool.py",
)
SCHEMA = "credproof.project-public-bundle/v1"
IGNORED = {".git", ".venv", "__pycache__", ".credproof"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(commit: str, path: str) -> bytes:
    return subprocess.run(["git", "show", f"{commit}:{path}"], check=True,
                          stdout=subprocess.PIPE).stdout


def tree_digest(root: Path) -> str:
    rows = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in IGNORED for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows.append((rel.as_posix(), sha(path.read_bytes())))
    return sha(json.dumps(rows, ensure_ascii=False).encode())


def write_json(path: Path, value: dict) -> None:
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-prefix", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output).resolve()
    if out.exists():
        raise SystemExit(f"output exists: {out}")
    out.mkdir(parents=True)
    source = {}
    for relative in FILES:
        source[relative] = git_blob(args.source_commit, f"{args.source_prefix}/{relative}")
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source[relative])
    source_report = json.loads(git_blob(
        args.source_commit, f"{args.source_prefix}/report.json").decode("utf-8"))
    source_report["project_tree_sha256"] = tree_digest(out / "project")
    source_report["publication"] = {
        "schema": SCHEMA,
        "kind": "derived-public-bundle",
        "source_commit": args.source_commit,
        "source_prefix": args.source_prefix,
        "source_validation_project_tree_sha256": source_report.get("final_validation", {}).get("project_tree_sha256"),
        "published_project_tree_sha256": source_report["project_tree_sha256"],
        "newline_policy": "Git blob bytes published as-is; entry semantic comparison may normalize CRLF to LF",
        "model_rerun": False,
    }
    write_json(out / "report.json", source_report)
    publication = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": args.source_commit,
        "source_prefix": args.source_prefix,
        "git_blob_sha256": {name: sha(data) for name, data in source.items()},
        "published_project_tree_sha256": tree_digest(out / "project"),
        "source_validation_project_tree_sha256": source_report["publication"]["source_validation_project_tree_sha256"],
        "entry_path": "project/tool.py",
        "entry_newline": "LF" if b"\r\n" not in source["project/tool.py"] else "CRLF",
        "entry_semantic_mapping": "The fixed Git blob is the publication byte source; no local checkout conversion is trusted.",
        "trust": "Git and the trusted checker identify bytes; hashes are not signatures or third-party certification",
    }
    write_json(out / "publication.json", publication)
    files = {}
    for path in sorted(out.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[path.relative_to(out).as_posix()] = sha(path.read_bytes())
    manifest = {
        "schema": SCHEMA,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_commit": args.source_commit,
        "source_prefix": args.source_prefix,
        "project_tree_sha256": tree_digest(out / "project"),
        "files": files,
        "publication": publication,
        "execution_performed": False,
        "trust": "trusted Git retrieval and checker; hashes detect changes, not authenticity",
    }
    write_json(out / "manifest.json", manifest)
    print(json.dumps({"output": str(out), "project_tree_sha256": manifest["project_tree_sha256"],
                      "files": len(files), "manifest_sha256": sha((out / "manifest.json").read_bytes())}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
