"""Anonymous, no-cookie verification of a fixed GitHub commit and bundle."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import argparse
from urllib.request import Request, urlopen


REPO = "tingfengy2000-creator/credproof"


def fetch(url: str) -> tuple[int, bytes, str]:
    request = Request(url, headers={"User-Agent": "CredProof-review-verifier/1.0", "Accept": "*/*"})
    with urlopen(request, timeout=20) as response:
        return response.status, response.read(), response.headers.get("Content-Type", "")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], check=True,
                            stdout=subprocess.PIPE, text=True).stdout.strip()
    raw_base = f"https://raw.githubusercontent.com/{REPO}/{commit}/"
    prefix = "docs/reusable-tool-safety/acceptance/20261006-live-correction/public-project-bundle-dev17/"
    fixed = [
        "docs/reusable-tool-safety/README.md",
        "credproof_safety/project_bundle.py",
        "agent_pilot/web.py",
        "agent_pilot/runtime_config.py",
        "docs/reusable-tool-safety/acceptance/20261006-live-correction/binding-regression-dev18.json",
        prefix + "manifest.json",
        prefix + "publication.json",
        prefix + "project/tool.py",
        "docs/reusable-tool-safety/acceptance/20261006-live-correction/public-project-recheck-dev17.json",
    ]
    fetched = {}
    for path in fixed:
        status, body, content_type = fetch(raw_base + path)
        fetched[path] = {"status": status, "bytes": len(body), "sha256": digest(body),
                         "content_type": content_type}
    manifest_path = prefix + "manifest.json"
    manifest = json.loads(fetch(raw_base + manifest_path)[1].decode("utf-8"))
    bundle_checks = {}
    for path, expected in manifest["files"].items():
        status, body, content_type = fetch(raw_base + prefix + path)
        bundle_checks[path] = {"status": status, "expected_sha256": expected,
                               "actual_sha256": digest(body), "bytes": len(body),
                               "content_type": content_type, "matches": digest(body) == expected}
    remote_ref = subprocess.run(["git", "ls-remote", "origin", "refs/heads/feat/reusable-tool-safety"],
                                check=True, stdout=subprocess.PIPE, text=True).stdout.strip()
    api_status, api_body, api_content = fetch(f"https://api.github.com/repos/{REPO}/commits/{commit}")
    api_commit = json.loads(api_body).get("sha") if api_status == 200 else None
    result = {
        "schema": "credproof.github-anonymous-verification/v1",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "repository": REPO,
        "commit": commit,
        "remote_branch_ref": remote_ref,
        "remote_branch_matches": remote_ref.startswith(commit + "\t"),
        "commit_api": {"status": api_status, "content_type": api_content, "sha": api_commit,
                       "matches": api_commit == commit},
        "fixed_paths": fetched,
        "bundle_manifest_path": manifest_path,
        "bundle_schema": manifest.get("schema"),
        "bundle_checks": bundle_checks,
        "all_bundle_bytes_match": all(item["matches"] for item in bundle_checks.values()),
        "readme_contains_dev18": b"dev18" in fetch(raw_base + "docs/reusable-tool-safety/README.md")[1],
        "authorization_headers_sent": False,
        "cookies_sent": False,
    }
    out = args.output or Path("docs/reusable-tool-safety/acceptance/20261006-live-correction/remote-verification-dev18.json")
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["remote_branch_matches"] and result["commit_api"]["matches"] and result["all_bundle_bytes_match"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
