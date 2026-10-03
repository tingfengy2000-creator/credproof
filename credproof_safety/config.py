from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import json
from pathlib import Path
import re
import tomllib


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_\.]*$")
_RELATIVE = re.compile(r"^[^\\/:*?\"<>|]+(?:[/\\][^\\/:*?\"<>|]+)*$")


@dataclass(frozen=True)
class ServiceRule:
    scheme: str
    host: str
    port: int
    path_prefix: str = "/"

    def as_dict(self) -> dict:
        return {"scheme": self.scheme, "host": self.host, "port": self.port,
                "path_prefix": self.path_prefix}


@dataclass(frozen=True)
class EntrySpec:
    module: str
    callable: str
    request: dict = field(default_factory=dict)
    expected_error: str | None = None


@dataclass(frozen=True)
class SafetyConfig:
    config_path: Path
    project_root: Path
    tests: tuple[str, ...]
    source_scope: tuple[str, ...]
    mutable_scope: tuple[str, ...]
    allowed_dirs: tuple[str, ...]
    forbidden_dirs: tuple[str, ...]
    require_allowed_file_read: bool
    services: tuple[ServiceRule, ...]
    require_service_credential: bool
    credential_env: str
    entry: EntrySpec
    timeout_seconds: float = 30.0
    report_dir: str = ".credproof"
    python: str = "python3"

    def to_public_dict(self) -> dict:
        return {
            "schema": "credproof.project-safety/v1",
            "project_root": ".",
            "tests": list(self.tests),
            "source_scope": list(self.source_scope),
            "mutable_scope": list(self.mutable_scope),
            "allowed_dirs": list(self.allowed_dirs),
            "forbidden_dirs": list(self.forbidden_dirs),
            "require_allowed_file_read": self.require_allowed_file_read,
            "services": [x.as_dict() for x in self.services],
            "require_service_credential": self.require_service_credential,
            "credential_env": self.credential_env,
            "entry": {"module": self.entry.module, "callable": self.entry.callable,
                       "request": self.entry.request, "expected_error": self.entry.expected_error},
            "timeout_seconds": self.timeout_seconds,
            "report_dir": self.report_dir,
            "python": self.python,
        }

    def matches_mutable(self, relative: str) -> bool:
        return any(fnmatch.fnmatchcase(relative.replace("\\", "/"), pattern)
                   for pattern in self.mutable_scope)

    def matches_source(self, relative: str) -> bool:
        return any(fnmatch.fnmatchcase(relative.replace("\\", "/"), pattern)
                   for pattern in self.source_scope)


def _strings(value, name, *, allow_empty=False) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
        raise ValueError(f"{name} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ValueError(f"{name} must not be empty")
    return tuple(x.replace("\\", "/") for x in value)


def _relative(value: str, name: str, *, glob=False) -> str:
    value = value.replace("\\", "/")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value.startswith("~"):
        raise ValueError(f"{name} must stay inside the project")
    if not value or value.startswith("/") or (not glob and not _RELATIVE.match(value)):
        raise ValueError(f"invalid relative path in {name}")
    return value


def _load_raw(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Configuration must be a regular file")
    if path.stat().st_size > 256 * 1024:
        raise ValueError("Configuration exceeds 256 KiB")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"invalid TOML configuration: {exc}") from exc
    if data.get("schema") != "credproof.project-safety/v1":
        raise ValueError("unsupported or missing credproof.toml schema")
    return data


def load_config(path: str | Path, *, project_root: str | Path | None = None) -> SafetyConfig:
    path = Path(path).absolute()
    if path.is_symlink():
        raise ValueError("Configuration must not be a symbolic link")
    path = path.resolve(strict=True)
    raw = _load_raw(path)
    if project_root is not None:
        root = Path(project_root).resolve(strict=True)
    else:
        root_value = raw.get("project", {}).get("root", ".")
        if not isinstance(root_value, str):
            raise ValueError("project.root must be a relative path")
        root_rel = _relative(root_value, "project.root") if root_value != "." else "."
        root = (path.parent / root_rel).resolve(strict=True)
    if path.parent.resolve() != root and not path.resolve().is_relative_to(root):
        raise ValueError("Configuration must belong to the selected project")
    project = raw.get("project", {})
    tests = tuple(_relative(x, "project.tests") for x in _strings(project.get("tests", ["tests"]), "project.tests"))
    source = tuple(_relative(x, "project.source_scope", glob=True)
                   for x in _strings(project.get("source_scope", ["**/*.py"]), "project.source_scope"))
    mutable = tuple(_relative(x, "project.mutable_scope", glob=True)
                    for x in _strings(project.get("mutable_scope", ["**/*.py"]), "project.mutable_scope"))
    files = raw.get("files", {})
    allowed = tuple(_relative(x, "files.allowed_dirs") for x in _strings(files.get("allowed_dirs", ["data"]), "files.allowed_dirs"))
    forbidden = tuple(_relative(x, "files.forbidden_dirs") for x in _strings(files.get("forbidden_dirs", ["secrets"]), "files.forbidden_dirs"))
    if set(allowed) & set(forbidden):
        raise ValueError("Allowed and forbidden directories overlap")
    network = raw.get("network", {})
    require_allowed_file_read = files.get("require_allowed_file_read", False)
    if not isinstance(require_allowed_file_read, bool):
        raise ValueError("files.require_allowed_file_read must be boolean")
    service_items = network.get("allowed_services", [])
    if not isinstance(service_items, list) or any(not isinstance(item, dict) for item in service_items):
        raise ValueError("network.allowed_services must be a list of tables")
    services = []
    for item in service_items:
        scheme, host, port = item.get("scheme"), item.get("host"), item.get("port")
        if scheme != "http" or host != "127.0.0.1":
            raise ValueError("Only the isolated 127.0.0.1 HTTP mock is supported")
        if port != 0:
            raise ValueError("The isolated service must use dynamic port 0")
        prefix = item.get("path_prefix", "/")
        if not isinstance(prefix, str) or not prefix.startswith("/") or ".." in Path(prefix).parts:
            raise ValueError("Invalid service path_prefix")
        services.append(ServiceRule(scheme, host, port, prefix))
    require_service_credential = network.get("require_service_credential", False)
    if not isinstance(require_service_credential, bool):
        raise ValueError("network.require_service_credential must be boolean")
    credentials = raw.get("credentials", {})
    credential_env = credentials.get("env", "CREDPROOF_TEST_CREDENTIAL")
    if not isinstance(credential_env, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{1,63}", credential_env):
        raise ValueError("credentials.env must be an uppercase environment variable name")
    entry = raw.get("entry", {})
    if not isinstance(entry, dict) or not _IDENT.fullmatch(str(entry.get("module", ""))) or not _IDENT.fullmatch(str(entry.get("callable", ""))):
        raise ValueError("entry.module and entry.callable must be import identifiers")
    request = entry.get("request", {})
    if not isinstance(request, dict):
        raise ValueError("entry.request must be a JSON object")
    expected_error = entry.get("expected_error")
    if expected_error is not None and (not isinstance(expected_error, str) or not _IDENT.fullmatch(expected_error)):
        raise ValueError("entry.expected_error must be a simple exception name")
    limits = raw.get("limits", {})
    timeout = limits.get("timeout_seconds", 30.0)
    if not isinstance(timeout, (int, float)) or not 0.2 <= timeout <= 120:
        raise ValueError("limits.timeout_seconds must be between 0.2 and 120")
    report_dir = limits.get("report_dir", raw.get("report_dir", ".credproof"))
    if not isinstance(report_dir, str) or Path(report_dir).is_absolute() or ".." in Path(report_dir).parts:
        raise ValueError("report_dir must stay inside the project")
    return SafetyConfig(path, root, tests, source, mutable, allowed, forbidden,
                        require_allowed_file_read, tuple(services), require_service_credential, credential_env,
                        EntrySpec(entry["module"], entry["callable"], request, expected_error),
                        float(timeout), report_dir, str(raw.get("python", "python3")))


def template(project_root: Path) -> str:
    return '''schema = "credproof.project-safety/v1"

[project]
root = "."
tests = ["tests"]
source_scope = ["**/*.py"]
mutable_scope = ["**/*.py"]

[files]
allowed_dirs = ["data"]
forbidden_dirs = ["secrets"]
require_allowed_file_read = true

[network]
require_service_credential = true
allowed_services = [
  { scheme = "http", host = "127.0.0.1", port = 0, path_prefix = "/api" },
]

[credentials]
env = "CREDPROOF_TEST_CREDENTIAL"

[entry]
module = "tool"
callable = "run"
request = { resource = "demo" }

[limits]
timeout_seconds = 30
report_dir = ".credproof"
'''


def preview(path: Path) -> dict:
    return {"path": str(path), "exists": path.exists(), "action": "would_create" if not path.exists() else "refuse_to_overwrite"}
