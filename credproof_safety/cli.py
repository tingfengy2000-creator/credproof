from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_config, preview, template
from .project import check_project, export_regression_tests
from .agent import request_repair


EXIT_PASS, EXIT_FAIL, EXIT_UNKNOWN, EXIT_ERROR = 0, 2, 3, 4


class _Parser(argparse.ArgumentParser):
    """Usage errors exit 4 (ERROR), never 2, which means a verified FAIL."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(EXIT_ERROR, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    p = _Parser(prog="credproof-safety", description="受控 Python 工具安全检查")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="预览或创建项目配置；默认不覆盖")
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--config", type=Path)
    init.add_argument("--write", action="store_true", help="仅在目标不存在时写入模板")
    check = sub.add_parser("check", help="在隔离副本执行 pytest 与配置入口")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--output", type=Path)
    check.add_argument("--source-root", type=Path, help="仓库根目录（默认当前目录）；派生格式中的路径相对于它")
    check.add_argument("--sarif", type=Path, help="写出 SARIF 2.1.0（只由本次报告派生）")
    check.add_argument("--junit", type=Path, help="写出 JUnit XML（只由本次报告派生）")
    check.add_argument("--summary", type=Path, help="写出 Markdown 摘要（只由本次报告派生）")
    export = sub.add_parser("export-tests", help="导出可重复运行的 pytest 回归断言")
    export.add_argument("--config", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    repair = sub.add_parser("repair", help="让本地模型提出候选并由程序复验")
    repair.add_argument("--config", type=Path, required=True)
    repair.add_argument("--output", type=Path)
    repair.add_argument("--strategy", choices=['qwen_agent', 'bounded_patch'], default='qwen_agent')
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            root = args.project.resolve(strict=True)
            cfg = (args.config or root / "credproof.toml").resolve()
            if not cfg.parent.is_relative_to(root):
                raise ValueError("--config must stay inside the selected project")
            if args.write and not cfg.exists():
                cfg.write_text(template(root), encoding="utf-8", newline="\n")
                result = {"status": "CREATED", "path": str(cfg)}
            else:
                result = preview(cfg)
            print(json.dumps(result, ensure_ascii=True, indent=2)); return 0
        if args.command == "check":
            derived = [x for x in (args.sarif, args.junit, args.summary) if x is not None]
            context = _format_context(args.config, args.source_root) if derived else None
            result = check_project(args.config, output=args.output)
            if context is not None:
                _write_formats(result, context, args)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            verdict = result.get("verdict")
            return EXIT_PASS if verdict == "PASS" else EXIT_FAIL if verdict == "FAIL" else EXIT_UNKNOWN
        if args.command == "export-tests":
            result = export_regression_tests(args.config, args.output)
            print(json.dumps({"status": "EXPORTED", "directory": str(result)}, ensure_ascii=True, indent=2)); return 0
        if args.command == "repair":
            result = request_repair(args.config, output=args.output, strategy=args.strategy)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result.get("status") == "OK" else 3
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return EXIT_ERROR
    return EXIT_ERROR


def _version() -> str:
    """Source checkout first (installed metadata may belong to another copy), then the wheel."""
    try:
        import tomllib
        project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project.get("name") == "credproof-safety":
            return str(project["version"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        import importlib.metadata
        return importlib.metadata.version("credproof-safety")
    except Exception:
        return "unknown"


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("--config and its entry file must be inside --source-root") from exc


def _format_context(config_path: Path, source_root: Path | None):
    """Trusted relative paths for derived formats; computed before the check runs."""
    from .report_formats import Context
    root = (source_root or Path.cwd()).resolve(strict=True)
    config_file = Path(config_path).resolve(strict=True)
    config = load_config(config_file)
    entry = (Path(config.project_root) / (config.entry.module.replace(".", "/") + ".py")).resolve()
    return Context(config_path=_relative(config_file, root), entry_path=_relative(entry, root), version=_version())


def _write_formats(result: dict, context, args) -> None:
    from .report_formats import to_junit, to_sarif, to_summary
    outputs = ((args.sarif, lambda: json.dumps(to_sarif(result, context), ensure_ascii=False, indent=2) + "\n"),
               (args.junit, lambda: to_junit(result, context)),
               (args.summary, lambda: to_summary(result, context)))
    for path, render in outputs:
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(render(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    raise SystemExit(main())
