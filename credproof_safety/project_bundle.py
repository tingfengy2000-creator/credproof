"""Self-contained export and recheck for a ``project-safety/v1`` task.

This format is deliberately separate from the historical thirteen-check
``portable-bundle`` format.  It carries the project candidate and its actual
configuration, then invokes the same trusted ``check_project`` function on a
fresh copy during recheck.  Hashes bind material; they are not signatures.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .project import check_project, _digest_tree

SCHEMA = "credproof.project-bundle/v1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _files(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "manifest.json"}


def _safe_copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir() or source.is_symlink():
        raise ValueError("candidate_project_unavailable")
    shutil.copytree(source, target, symlinks=False,
                    ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", ".credproof", "*.pyc"))
    for path in target.rglob("*"):
        if path.is_symlink():
            raise ValueError("candidate_project_symlink_unsupported")
        if path.is_file() and path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("candidate_project_file_too_large")


def export_project_bundle(method: str | Path, output: str | Path) -> dict:
    method = Path(method).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or not method.is_dir():
        raise ValueError("new_project_bundle_output_required")
    row = json.loads((method / "result.json").read_text(encoding="utf-8"))
    if row.get("schema") != "credproof.web-live-record/v1":
        raise ValueError("project_live_record_required")
    artifact_value = row.get("artifact_dir")
    if not isinstance(artifact_value, str):
        raise ValueError("candidate_artifact_reference_missing")
    candidate = Path(artifact_value).resolve(strict=True) / "candidate"
    if not candidate.is_dir():
        raise ValueError("candidate_project_missing")
    original = (method / "original.py").read_bytes()
    current = (method / "final-candidate.py").read_bytes()
    output.mkdir(parents=True)
    project = output / "project"
    _safe_copy_tree(candidate, project)
    (output / "original.py").write_bytes(original)
    (output / "candidate.py").write_bytes(current)
    public_row = {k: row.get(k) for k in (
        "schema", "project_id", "case_id", "initial_authority", "diagnosis",
        "final_validation", "task", "model", "execution_counts", "web_adapter",
        "source_sha256", "candidate_sha256", "candidate_count", "execution_kind")}
    try:
        from .web_repair import execution_summary
        counts = execution_summary(row)
        public_row["execution_counts"] = counts
        public_row["candidate_count"] = counts.get("accepted_candidates", 0)
    except (ImportError, OSError, ValueError, TypeError):
        pass
    public_row["exported_at"] = _now()
    public_row["project_tree_sha256"] = _digest_tree(candidate)
    public_row["artifact_material"] = "project/; raw model workspace is intentionally excluded"
    _json(output / "report.json", public_row)
    _json(output / "configuration.json", {"schema": SCHEMA, "project_config": "project/credproof.toml",
          "checker": "credproof_safety.check_project", "fresh_recheck": True,
          "trust": "trusted checker and operator; hashes detect changes, not authenticity"})
    manifest = {"schema": SCHEMA, "created_at": _now(), "source_sha256": _sha(original),
                "candidate_sha256": _sha(current), "project_tree_sha256": _digest_tree(project),
                "files": _files(output), "execution_performed": False,
                "trust": "trusted checker and operator; hashes are not signatures"}
    _json(output / "manifest.json", manifest)
    return {"status": "EXPORTED", "schema": SCHEMA, "bundle_path": str(output),
            "project_tree_sha256": manifest["project_tree_sha256"], "files": len(manifest["files"])}


def recheck_project_bundle(bundle: str | Path, output: str | Path) -> dict:
    root = Path(bundle).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or not (root / "manifest.json").is_file():
        raise ValueError("new_recheck_output_and_manifest_required")
    reasons: list[str] = []
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        report = json.loads((root / "report.json").read_text(encoding="utf-8"))
        if manifest.get("schema") != SCHEMA:
            raise ValueError("unsupported_project_bundle_schema")
        for name, digest in manifest.get("files", {}).items():
            path = root / name
            if not path.is_file() or _sha(path.read_bytes()) != digest:
                reasons.append("MATERIAL_CHANGED:" + name)
        project = root / "project"
        current_tree = _digest_tree(project) if project.is_dir() else None
        if current_tree != manifest.get("project_tree_sha256"):
            reasons.append("PROJECT_OBJECT_CHANGED")
        prior = not reasons and current_tree == report.get("project_tree_sha256", current_tree)
        if reasons:
            validation = {"verdict": "UNKNOWN", "reasons": reasons, "checks": []}
        else:
            fresh_path = root / (".fresh-" + next(tempfile._get_candidate_names()) + ".json")
            fresh = check_project(project / "credproof.toml", output=fresh_path, project_root=project)
            fresh_path.unlink(missing_ok=True)
            validation = fresh
        result = {"schema": "credproof.project-recheck/v1", "status": "RECHECKED",
                  "checked_at": _now(), "validation": validation,
                  "candidate_sha256": manifest.get("candidate_sha256"),
                  "project_tree_sha256": current_tree, "prior_report_applicable": prior,
                  "prior_report_reasons": reasons, "historical_task_status_rewritten": False,
                  "trust_boundary": "trusted checker/operator; hashes are not authenticity"}
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        result = {"schema": "credproof.project-recheck/v1", "status": "BLOCKED",
                  "checked_at": _now(), "validation": {"verdict": "UNKNOWN", "reasons": ["MATERIAL_UNAVAILABLE"], "checks": []},
                  "prior_report_applicable": False, "prior_report_reasons": ["MATERIAL_UNAVAILABLE"],
                  "historical_task_status_rewritten": False}
    _json(output, result)
    return result
