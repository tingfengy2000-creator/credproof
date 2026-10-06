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

from .config import load_config
from .project import check_project, _digest_tree

SCHEMA = "credproof.project-bundle/v1"
PUBLIC_SCHEMA = "credproof.project-public-bundle/v1"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _files(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): _sha(p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file() and p.name != "manifest.json"}


def _normal_text(data: bytes) -> bytes:
    """Normalize only for comparing a generated entry across newline styles."""
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _newline_style(data: bytes) -> str:
    if b"\r\n" in data:
        return "CRLF"
    if b"\r" in data:
        return "CR"
    return "LF"


def _safe_relative(root: Path, name: str) -> Path:
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("invalid_manifest_path")
    relative = Path(name)
    if ".." in relative.parts:
        raise ValueError("invalid_manifest_path")
    raw_path = root / relative
    if raw_path.is_symlink():
        raise ValueError("manifest_symlink_unsupported")
    path = raw_path.resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("invalid_manifest_path")
    return path


def _config_public(candidate: Path) -> tuple[Path, dict]:
    config_path = candidate / "credproof.toml"
    if not config_path.is_file():
        raise ValueError("candidate_configuration_missing")
    config = load_config(config_path, project_root=candidate)
    return config_path, config.to_public_dict()


def _bind_validation_object(row: dict, candidate: Path, current: bytes) -> dict:
    """Verify that the recorded verdict belongs to the exact candidate object.

    The live record is not trusted merely because it contains a verdict.  The
    final validation tree, configuration and entry must agree with the actual
    artifact before anything is copied into a public bundle.
    """
    final = row.get("final_validation")
    if not isinstance(final, dict):
        raise ValueError("final_validation_missing")
    recorded_tree = final.get("project_tree_sha256")
    if not isinstance(recorded_tree, str) or len(recorded_tree) != 64:
        raise ValueError("final_validation_project_tree_missing")
    actual_tree = _digest_tree(candidate)
    if actual_tree != recorded_tree:
        raise ValueError("final_validation_project_tree_mismatch")
    config_path, config_public = _config_public(candidate)
    recorded_config = final.get("config")
    if not isinstance(recorded_config, dict) or recorded_config != config_public:
        raise ValueError("final_validation_configuration_mismatch")
    entry_rel = Path(config_public["entry"]["module"].replace(".", "/") + ".py")
    entry = candidate / entry_rel
    if not entry.is_file() or not entry.resolve().is_relative_to(candidate.resolve()):
        raise ValueError("final_validation_entry_missing")
    candidate_entry = entry.read_bytes()
    normalized_equal = _normal_text(candidate_entry) == _normal_text(current)
    if not normalized_equal:
        raise ValueError("final_validation_entry_mismatch")
    test_paths = [str(candidate / item) for item in config_public["tests"]]
    if any(not Path(item).exists() for item in test_paths):
        raise ValueError("final_validation_required_tests_missing")
    return {
        "validation_project_tree_sha256": recorded_tree,
        "candidate_project_tree_sha256": actual_tree,
        "config_path": "project/credproof.toml",
        "config_sha256": _sha(config_path.read_bytes()),
        "required_test_paths": list(config_public["tests"]),
        "entry_path": (Path("project") / entry_rel).as_posix(),
        "entry_source_sha256": _sha(current),
        "entry_candidate_sha256": _sha(candidate_entry),
        "entry_source_newline": _newline_style(current),
        "entry_candidate_newline": _newline_style(candidate_entry),
        "entry_newline_policy": "LF-normalized comparison only; project bytes remain unchanged",
        "entry_normalized_equal": True,
    }


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
    binding = _bind_validation_object(row, candidate, current)
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
    public_row["object_binding"] = binding
    public_row["artifact_material"] = "project/; raw model workspace is intentionally excluded"
    _json(output / "report.json", public_row)
    _json(output / "configuration.json", {"schema": SCHEMA, "project_config": "project/credproof.toml",
          "checker": "credproof_safety.check_project", "fresh_recheck": True,
          "trust": "trusted checker and operator; hashes detect changes, not authenticity"})
    copied_tree = _digest_tree(project)
    if copied_tree != binding["candidate_project_tree_sha256"]:
        raise ValueError("copied_project_tree_mismatch")
    manifest = {"schema": SCHEMA, "created_at": _now(), "source_sha256": _sha(original),
                "candidate_sha256": _sha(current), "project_tree_sha256": _digest_tree(project),
                "object_binding": binding,
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
        if manifest.get("schema") not in {SCHEMA, PUBLIC_SCHEMA}:
            raise ValueError("unsupported_project_bundle_schema")
        files = manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("manifest_files_missing")
        for name, digest in files.items():
            path = _safe_relative(root, name)
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
