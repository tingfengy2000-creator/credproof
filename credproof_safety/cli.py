from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_config, preview, template
from .project import check_project, export_regression_tests
from .agent import request_repair


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="credproof-safety", description="受控 Python 工具安全检查")
    sub = p.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init", help="预览或创建项目配置；默认不覆盖")
    init.add_argument("--project", type=Path, required=True)
    init.add_argument("--config", type=Path)
    init.add_argument("--write", action="store_true", help="仅在目标不存在时写入模板")
    check = sub.add_parser("check", help="在隔离副本执行 pytest 与配置入口")
    check.add_argument("--config", type=Path, required=True)
    check.add_argument("--output", type=Path)
    export = sub.add_parser("export-tests", help="导出可重复运行的 pytest 回归断言")
    export.add_argument("--config", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    repair = sub.add_parser("repair", help="让本地模型提出候选并由程序复验")
    repair.add_argument("--config", type=Path, required=True)
    repair.add_argument("--output", type=Path)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            root = args.project.resolve(strict=True)
            cfg = (args.config or root / "credproof.toml").resolve()
            if args.write and not cfg.exists():
                cfg.write_text(template(root), encoding="utf-8", newline="\n")
                result = {"status": "CREATED", "path": str(cfg)}
            else:
                result = preview(cfg)
            print(json.dumps(result, ensure_ascii=True, indent=2)); return 0
        if args.command == "check":
            result = check_project(args.config, output=args.output)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result.get("verdict") == "PASS" else 2 if result.get("verdict") == "FAIL" else 3
        if args.command == "export-tests":
            result = export_regression_tests(args.config, args.output)
            print(json.dumps({"status": "EXPORTED", "directory": str(result)}, ensure_ascii=True, indent=2)); return 0
        if args.command == "repair":
            result = request_repair(args.config, output=args.output)
            print(json.dumps(result, ensure_ascii=True, indent=2))
            return 0 if result.get("status") == "OK" else 3
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "ERROR", "error": str(exc)}, ensure_ascii=True), file=sys.stderr)
        return 4
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
