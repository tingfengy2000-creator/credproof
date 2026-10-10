#!/usr/bin/env python3
"""Derive a byte-stable public project bundle from a fixed Git commit.

This intentionally reads every source material through ``git show`` rather than
from a Windows checkout.  The repository's text attributes therefore define the
published LF bytes, while the original local bundle remains untouched.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import sys


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def digest_tree(root: Path) -> str:
    rows = []
    ignored = {".git", ".venv", "__pycache__", ".credproof"}
    # Match the checker's host-independent, legacy-Windows ordering.  Exact
    # relative spelling and file bytes remain part of the identity.
    order = lambda path: (tuple(part.lower() for part in path.relative_to(root).parts),
                          path.relative_to(root).as_posix())
    for path in sorted(root.rglob("*"), key=order):
        rel = path.relative_to(root)
        if any(part in ignored for part in rel.parts):
            continue
        if path.is_file() and not path.is_symlink():
            rows.append((rel.as_posix(), sha(path.read_bytes())))
    return sha(json.dumps(rows, ensure_ascii=False).encode())


def git_bytes(repo: Path, commit: str, relative: str) -> bytes:
    # Validate the path before passing it to Git.  It must be a repository-local
    # POSIX path from the old manifest, never an arbitrary user path.
    rel = PurePosixPath(relative)
    if rel.is_absolute() or ".." in rel.parts or not relative:
        raise ValueError(f"unsafe source path: {relative!r}")
    return subprocess.check_output(
        ["git", "-C", str(repo), "show", f"{commit}:{relative}"],
        stderr=subprocess.STDOUT,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=Path.cwd())
    ap.add_argument("--commit", required=True)
    ap.add_argument("--source-bundle", type=Path, required=True)
    ap.add_argument("--source-prefix", required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    repo = args.repo.resolve()
    source = args.source_bundle.resolve(strict=True)
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    old_manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    # Keep both hashes: the checkout may contain CRLF, while the fixed Git
    # commit contains the LF blob that is used for publication provenance.
    old_manifest_local_sha = sha((source / "manifest.json").read_bytes())
    old_manifest_git = git_bytes(repo, args.commit, f"{args.source_prefix}/manifest.json")
    old_manifest_git_sha = sha(old_manifest_git)
    file_names = list(old_manifest.get("files", {}))
    if not file_names or any(name in {"manifest.json", "publication.json"} for name in file_names):
        raise SystemExit("unexpected source manifest file list")

    output.mkdir(parents=True)
    published = {}
    git_source_hashes = {}
    for name in sorted(file_names):
        target = output / Path(name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = git_bytes(repo, args.commit, f"{args.source_prefix}/{name}")
        target.write_bytes(data)
        published[name] = sha(data)
        git_source_hashes[name] = published[name]

    # The old report is a historical execution record.  Update only the public
    # tree binding and append an explicit derivation record; final_validation is
    # preserved so the old run is not silently rewritten.
    report_path = output / "report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    public_tree = digest_tree(output / "project")
    report["project_tree_sha256"] = public_tree
    report["public_derivation"] = {
        "schema": "credproof.project-public-bundle-derivation/v1",
        "source_commit": args.commit,
        "source_bundle_manifest_local_sha256": old_manifest_local_sha,
        "source_bundle_manifest_git_sha256": old_manifest_git_sha,
        "source_project_tree_sha256": old_manifest.get("project_tree_sha256"),
        "published_project_tree_sha256": public_tree,
        "entry_path": "project/tool.py",
        "source_entry_sha256": old_manifest.get("files", {}).get("project/tool.py"),
        "published_entry_sha256": published.get("project/tool.py"),
        "source_entry_newline": old_manifest.get("object_binding", {}).get("entry_candidate_newline", "CRLF"),
        "published_entry_newline": "LF",
        "newline_policy": "Git blob bytes are authoritative; no checkout newline conversion is trusted",
        "historical_final_validation_preserved": True,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    publication = {
        "schema": "credproof.project-public-bundle/v1",
        "source_commit": args.commit,
        "source_prefix": args.source_prefix,
        "source_bundle_manifest_local_sha256": old_manifest_local_sha,
        "source_bundle_manifest_git_sha256": old_manifest_git_sha,
        "source_validation_project_tree_sha256": old_manifest.get("project_tree_sha256"),
        "published_project_tree_sha256": public_tree,
        "entry_path": "project/tool.py",
        "entry_newline": "LF",
        "entry_semantic_mapping": "The fixed Git blob is the publication byte source; no local checkout conversion is trusted.",
        # report.json is intentionally rewritten below to bind the public tree;
        # retain its source Git hash separately instead of claiming the derived
        # report bytes are unchanged.
        "git_blob_sha256": {k: v for k, v in git_source_hashes.items() if k != "report.json"},
        "source_report_git_sha256": git_source_hashes.get("report.json"),
        "source_entry_sha256": old_manifest.get("files", {}).get("project/tool.py"),
        "published_entry_sha256": published.get("project/tool.py"),
        "newline_policy": "Only the public Git-byte representation is changed; the old local bundle and its CRLF receipt remain unchanged.",
        "trust": "Git and the trusted checker identify bytes; hashes are not signatures or third-party certification",
    }
    pub_path = output / "publication.json"
    pub_path.write_text(json.dumps(publication, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    published["publication.json"] = sha(pub_path.read_bytes())
    published["report.json"] = sha(report_path.read_bytes())

    manifest = {
        "schema": "credproof.project-public-bundle/v1",
        "source_commit": args.commit,
        "source_prefix": args.source_prefix,
        "source_bundle_manifest_local_sha256": old_manifest_local_sha,
        "source_bundle_manifest_git_sha256": old_manifest_git_sha,
        "source_project_tree_sha256": old_manifest.get("project_tree_sha256"),
        "project_tree_sha256": public_tree,
        "candidate_sha256": published.get("candidate.py"),
        "publication": publication,
        "files": published,
        "execution_performed": False,
        "trust": "trusted Git retrieval and checker; hashes detect changes, not authenticity",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({
        "output": str(output),
        "source_commit": args.commit,
        "source_bundle_manifest_local_sha256": old_manifest_local_sha,
        "source_bundle_manifest_git_sha256": old_manifest_git_sha,
        "published_project_tree_sha256": public_tree,
        "entry_sha256": published.get("project/tool.py"),
        "entry_bytes": len((output / "project/tool.py").read_bytes()),
        "entry_crlf_count": (output / "project/tool.py").read_bytes().count(b"\\r\\n"),
        "files": len(published),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
