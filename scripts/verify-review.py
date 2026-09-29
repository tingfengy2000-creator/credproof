#!/usr/bin/env python3
"""Verify every extracted review file without Git, network access or dependencies.

Run before installing dependencies or generating runs: extra files are rejected.
This checks integrity relative to the manifest, not publisher authenticity.
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import unicodedata


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(path.read_bytes().decode("utf-8"), object_pairs_hook=reject_duplicates)


def safe_path(name):
    if not isinstance(name, str) or not name:
        raise ValueError("Manifest path must be a nonempty string")
    path = PurePosixPath(name)
    if path.is_absolute() or str(path) != name:
        raise ValueError("Non-canonical path: " + repr(name))
    for part in path.parts:
        if (part in {".", ".."} or part.endswith((".", " "))
                or any(ord(char) < 32 or char in '<>:"\\|?*' for char in part)
                or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])", part.split(".")[0])):
            raise ValueError("Unsafe path: " + repr(name))
    return path


def regular_tree(root):
    """lstat before descending: do not follow symlinks or Windows junctions."""
    files, directories, pending = set(), set(), [root]
    while pending:
        directory = pending.pop()
        for child in directory.iterdir():
            info = child.lstat()
            name = child.relative_to(root).as_posix()
            safe_path(name)
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("Symlink/reparse point forbidden: " + name)
            if stat.S_ISDIR(info.st_mode):
                directories.add(name)
                pending.append(child)
            elif stat.S_ISREG(info.st_mode):
                files.add(name)
            else:
                raise ValueError("Non-regular file forbidden: " + name)
    return files, directories


def digest_file(path):
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def verify(root):
    # Check the caller's root itself before resolve() could hide a symlink.
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("Extraction root must be a real directory, not a symlink/junction")
    root = root.resolve(strict=True)
    actual, actual_dirs = regular_tree(root)
    if "manifest.json" not in actual:
        raise ValueError("Missing manifest.json")
    manifest = read_json(root / "manifest.json")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "credproof-review-manifest/v1":
        raise ValueError("Unsupported manifest schema")
    commit = manifest.get("review_commit", "")
    if not isinstance(commit, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError("Manifest does not contain a complete commit ID")
    records = manifest.get("files")
    if not isinstance(records, list) or not records:
        raise ValueError("Manifest files must be a nonempty list")
    expected, expected_dirs, identities = {"manifest.json"}, set(), {"manifest.json"}
    source_names, metadata_count = [], 0
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Invalid file record")
        name = record.get("path")
        path = safe_path(name)
        identity = unicodedata.normalize("NFC", name).casefold()
        if identity in identities:
            raise ValueError("Duplicate/colliding manifest path: " + name)
        identities.add(identity)
        expected.add(name)
        expected_dirs.update(parent.as_posix() for parent in path.parents if str(parent) != ".")
        size, digest = record.get("size"), record.get("sha256")
        if (type(size) is not int or size < 0 or not isinstance(digest, str)
                or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise ValueError("Invalid size/hash: " + name)
        if record.get("kind") == "metadata" and name == "release-metadata.json":
            metadata_count += 1
        elif record.get("kind") == "source" and name != "release-metadata.json":
            oid = record.get("git_blob_oid", "")
            if (record.get("git_mode") not in {"100644", "100755"}
                    or not isinstance(oid, str)
                    or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", oid)):
                raise ValueError("Invalid source provenance: " + name)
            source_names.append(name)
        else:
            raise ValueError("Invalid record kind: " + name)
    if metadata_count != 1 or sorted(source_names) != manifest.get("included_source_paths"):
        raise ValueError("Metadata or included-source list is inconsistent")
    if actual != expected:
        raise ValueError("File inventory mismatch: missing=" + repr(sorted(expected - actual))
                         + "; extra=" + repr(sorted(actual - expected)))
    if actual_dirs != expected_dirs:
        raise ValueError("Unexpected or missing directories: "
                         + repr(sorted(actual_dirs ^ expected_dirs)))
    for record in records:
        path = root.joinpath(*PurePosixPath(record["path"]).parts)
        if not path.resolve(strict=True).is_relative_to(root):
            raise ValueError("Path escapes extraction root: " + record["path"])
        size, digest = digest_file(path)
        if size != record["size"] or digest != record["sha256"]:
            raise ValueError("Size/SHA-256 mismatch: " + record["path"])
    metadata = read_json(root / "release-metadata.json")
    if (not isinstance(metadata, dict)
            or metadata.get("schema_version") != "credproof-review-metadata/v1"
            or metadata.get("review_commit") != commit):
        raise ValueError("Release metadata does not match manifest commit")
    print(json.dumps({"status": "PASS", "review_commit": commit,
                      "verified_files": len(records), "source_files": len(source_names),
                      "manifest_sha256": hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest()}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Freshly extracted review root")
    args = parser.parse_args()
    try:
        verify(args.root)
    except (OSError, ValueError, UnicodeError, RecursionError) as error:
        print("VERIFY FAILED: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
