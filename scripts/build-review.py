#!/usr/bin/env python3
"""Build a review ZIP from raw Git blobs, never from working-tree file bytes."""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlsplit
import zipfile


SOURCE_COMMIT = "f1a1099c0efbade56f1a5eb14b5a6f1210f05843"
EXCLUDED_DIRS = {
    ".git", "runs", ".venv", "venv", "env", "virtualenv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".cache",
    ".tox", ".nox", ".tools", ".codex", ".aws", ".ssh", "site-packages",
    "models", "model_weights", "checkpoints", "private_data", "snapshots",
    "repair_copies", "keys", "secrets", "credentials", "dist", "build",
    ".next", "coverage", ".idea", ".vscode",
}
EXCLUDED_SUFFIXES = {
    ".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".gguf",
    ".safetensors", ".pt", ".pth", ".ckpt", ".onnx", ".pyc", ".pyo", ".pyd",
    ".sqlite", ".sqlite3", ".db", ".log", ".zip",
}
EXCLUDED_NAMES = {
    "credentials.json", "local_settings.json", "id_rsa", "id_dsa",
    "id_ecdsa", "id_ed25519", ".git-credentials", ".netrc", ".npmrc",
    ".pypirc", ".ds_store", "thumbs.db", "pyvenv.cfg", "pytorch_model.bin", "tf_model.h5",
}
SAFE_ENV_EXAMPLES = {".env.example", ".env.sample"}
GENERATED_NAMES = {"manifest.json", "release-metadata.json"}


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
            + "\n").encode("utf-8")


def git(repo, *args):
    result = subprocess.run(
        ["git", "--no-replace-objects", "-C", str(repo), *args], check=False,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if result.returncode:
        raise ValueError("Git failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def resolve_commit(repo, revision):
    if not revision or any(ord(char) < 32 for char in revision):
        raise ValueError("Invalid commit argument")
    resolved = git(repo, "rev-parse", "--verify", "--end-of-options",
                   revision + "^{commit}").decode("ascii").strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", resolved):
        raise ValueError("Git did not resolve a complete commit object ID")
    return resolved


def safe_path(name):
    path = PurePosixPath(name)
    if not name or path.is_absolute() or str(path) != name:
        raise ValueError("Non-canonical archive path: " + repr(name))
    for part in path.parts:
        if (part in {".", ".."} or part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>:"\\|?*' for char in part)
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])",
                                part.split(".")[0])):
            raise ValueError("Unsafe archive path: " + repr(name))
    return path


def exclusion_reason(path):
    lowered = [part.casefold() for part in path.parts]
    for part in lowered:
        if part in EXCLUDED_DIRS:
            return "excluded directory/component: " + part
    leaf = lowered[-1]
    if leaf in SAFE_ENV_EXAMPLES:
        return None
    if leaf == ".env" or leaf.startswith(".env.") or leaf.endswith(".env"):
        return "environment configuration (not an approved example)"
    if leaf in EXCLUDED_NAMES:
        return "private/local filename: " + leaf
    if path.suffix.casefold() in EXCLUDED_SUFFIXES:
        return "private/generated/model suffix: " + path.suffix.casefold()
    return None


def file_record(name, data, kind, **extra):
    return {"path": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "kind": kind, **extra}


def zip_entry(archive, name, data, executable, date_tuple):
    info = zipfile.ZipInfo(name, date_time=date_tuple)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
    info.compress_type = zipfile.ZIP_DEFLATED
    archive.writestr(info, data)


def build(args):
    repo = args.repo.resolve(strict=True)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.version):
        raise ValueError("Version must be a safe filename component")
    if not args.tag or any(ord(char) < 32 for char in args.tag):
        raise ValueError("Tag must be a nonempty single-line label")
    url = urlsplit(args.repo_url)
    if (url.scheme != "https" or not url.hostname or url.username or url.password
            or url.query or url.fragment):
        raise ValueError("Repository URL must be HTTPS without credentials, query or fragment")
    commit = resolve_commit(repo, args.commit)
    source_commit = resolve_commit(repo, args.source_workspace_commit)
    entries, excluded, seen = [], [], {}
    # ls-tree names are NUL-delimited; cat-file returns original blob bytes, unlike
    # a checkout (newline filters) or archive with export-subst attributes.
    for record in git(repo, "ls-tree", "-r", "-z", "--full-tree", commit).split(b"\0"):
        if not record:
            continue
        header, raw_name = record.split(b"\t", 1)
        mode, object_type, oid = header.decode("ascii").split()
        name = raw_name.decode("utf-8", "strict")
        path = safe_path(name)
        identity = unicodedata.normalize("NFC", name).casefold()
        for component in [*reversed(path.parents), path]:
            spelling = str(component)
            if spelling == ".":
                continue
            folded = unicodedata.normalize("NFC", spelling).casefold()
            if folded in seen and seen[folded] != spelling:
                raise ValueError("Cross-platform path collision: " + name)
            seen[folded] = spelling
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise ValueError("Symlinks, submodules and non-regular entries are forbidden: " + name)
        if identity in GENERATED_NAMES:
            raise ValueError("Commit conflicts with generated release filename: " + name)
        entry = {"path": name, "git_mode": mode, "git_blob_oid": oid}
        reason = exclusion_reason(path)
        if reason:
            excluded.append({**entry, "reason": reason})
        else:
            entries.append(entry)
    entries.sort(key=lambda item: item["path"])
    excluded.sort(key=lambda item: item["path"])
    if not entries:
        raise ValueError("No eligible tracked files in commit")

    now = datetime.now(timezone.utc)
    local_now = now.astimezone()
    zip_name = f"credproof-{args.version}-{local_now:%Y%m%d}-{commit[:12]}.zip"
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    targets = [output / zip_name, output / "manifest.json", output / "sha256sums.txt"]
    if any(path.exists() or path.is_symlink() for path in targets):
        raise ValueError("Output already exists; choose a new output directory (no overwrite)")
    metadata = {
        "schema_version": "credproof-review-metadata/v1",
        "version": args.version, "tag": args.tag, "review_commit": commit,
        "source_workspace_commit": source_commit, "repository_url": args.repo_url,
        "built_at_utc": now.isoformat(), "build_local_date": local_now.date().isoformat(),
        "build_environment": {
            "python": platform.python_version(), "implementation": platform.python_implementation(),
            "system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "git": git(repo, "--version").decode("utf-8").strip(),
        },
        "build_command": ["python", "scripts/build-review.py", "--commit", commit,
                          "--version", args.version, "--tag", args.tag,
                          "--repo-url", args.repo_url, "--source-workspace-commit", source_commit,
                          "--repo", ".", "--output-dir", "<new-output-directory>"],
        "command_note": "Reproduction command; machine-local paths replaced by placeholders.",
        "source_policy": "Raw tracked Git blob bytes at review_commit; no working-tree source reads.",
        "historical_experiments": {
            "rerun_during_build": False,
            "notice": "Included historical experiment artifacts are not results of a rerun for this release.",
        },
        "exclusion_rules": {
            "directory_components_case_insensitive": sorted(EXCLUDED_DIRS),
            "suffixes_case_insensitive": sorted(EXCLUDED_SUFFIXES),
            "filenames_case_insensitive": sorted(EXCLUDED_NAMES),
            "environment_files": ".env, .env.*, *.env except the approved example basenames",
            "approved_environment_examples": sorted(SAFE_ENV_EXAMPLES),
            "note": "Path-based packaging exclusions are not a credential-content audit.",
        },
    }
    metadata_data = json_bytes(metadata)
    records, created = [], []
    try:
        # Exclusive creation remains safe if another build wins the preflight race.
        with targets[0].open("xb") as output_file:
            created.append(targets[0])
            with zipfile.ZipFile(output_file, "w") as archive:
                for entry in entries:
                    data = git(repo, "cat-file", "blob", entry["git_blob_oid"])
                    records.append(file_record(entry["path"], data, "source",
                                               git_mode=entry["git_mode"], git_blob_oid=entry["git_blob_oid"]))
                    zip_entry(archive, entry["path"], data, entry["git_mode"] == "100755",
                              local_now.timetuple()[:6])
                records.append(file_record("release-metadata.json", metadata_data, "metadata"))
                zip_entry(archive, "release-metadata.json", metadata_data, False, local_now.timetuple()[:6])
                manifest = {
                    "schema_version": "credproof-review-manifest/v1", "review_commit": commit,
                    "files": sorted(records, key=lambda item: item["path"]),
                    "included_source_paths": [entry["path"] for entry in entries],
                    "excluded": excluded,
                    "manifest_note": "manifest.json does not hash itself; external sha256sums.txt hashes it and the ZIP.",
                }
                manifest_data = json_bytes(manifest)
                zip_entry(archive, "manifest.json", manifest_data, False, local_now.timetuple()[:6])
        with targets[1].open("xb") as handle:
            created.append(targets[1])
            handle.write(manifest_data)
        zip_digest = hashlib.sha256(targets[0].read_bytes()).hexdigest()
        checksums = (f"{zip_digest}  {zip_name}\n"
                     f"{hashlib.sha256(manifest_data).hexdigest()}  manifest.json\n")
        with targets[2].open("xb") as handle:
            created.append(targets[2])
            handle.write(checksums.encode("utf-8"))
    except Exception:
        for path in reversed(created):
            path.unlink()
        raise
    print(json.dumps({"zip": str(targets[0]), "manifest": str(targets[1]),
                      "checksums": str(targets[2]), "review_commit": commit,
                      "source_files": len(entries), "excluded_files": len(excluded)}, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True, help="Commit/ref resolved once to a complete Git commit ID")
    parser.add_argument("--version", default="0.1.0-review.1")
    parser.add_argument("--tag", required=True, help="Release label recorded in metadata; no tag is created")
    parser.add_argument("--repo-url", required=True)
    parser.add_argument("--source-workspace-commit", default=SOURCE_COMMIT)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        print("BUILD FAILED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
