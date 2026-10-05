"""Thin loopback workspace for operator-selected projects; uses the CLI checker."""
from __future__ import annotations

import difflib
import hashlib
import json
from pathlib import Path
import uuid
import zipfile

from credproof_safety.config import load_config
from credproof_safety.project import _copy_project, _digest_tree, check_project, export_regression_tests


class ProjectWorkspace:
    def __init__(self, root, *, config_path=None, examples=False):
        self.root = Path(root)
        self.store = self.root / 'runs/project-workspace'
        self.projects = {}
        if examples:
            for key, folder, label, origin in (
                ('assistant-original', 'material_assistant', '资料助手 · 问题版本', '本项目合成样例'),
                ('assistant-fixed', 'material_assistant_fixed', '资料助手 · 预置修复示例', '人工预置修复；不是现场模型生成'),
            ):
                cfg = self.root / 'examples' / folder / 'credproof.toml'
                if cfg.is_file():
                    self.projects[key] = (cfg, label, origin)
        if config_path:
            cfg = Path(config_path).resolve(strict=True)
            load_config(cfg)  # operator authorization comes only from the launch argv
            self.projects['authorized-project'] = (cfg, '启动时授权的项目', '开发者通过 --project-config 明确选择')
        self.results = {}

    def _entry(self, key):
        if key not in self.projects:
            raise ValueError('Project is not registered by the local operator')
        path, label, origin = self.projects[key]
        return load_config(path), label, origin

    def describe(self, key):
        cfg, label, origin = self._entry(key)
        entry = cfg.project_root / (cfg.entry.module.replace('.', '/') + '.py')
        source = entry.read_text('utf-8') if entry.is_file() else ''
        if len(source) > 131072:
            raise ValueError('Entry source exceeds display limit')
        report = self.results.get(key)
        identity = _digest_tree(cfg.project_root)
        applicable = bool(report and report['input_identity'] == identity)
        diff = ''
        if key == 'assistant-fixed' and 'assistant-original' in self.projects:
            before_cfg, _, _ = self._entry('assistant-original')
            before = (before_cfg.project_root / 'tool.py').read_text('utf-8')
            diff = ''.join(difflib.unified_diff(before.splitlines(True), source.splitlines(True),
                                              fromfile='problem/tool.py', tofile='prepared-fix/tool.py'))
        return {'id': key, 'label': label, 'patch_origin': origin, 'config': cfg.to_public_dict(),
                'object_sha256': identity, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                'source_code': source, 'diff': diff, 'last_report': report['report'] if report else None,
                'last_report_applicable': applicable, 'mode': 'CURRENT_PROJECT',
                'notice': '上次检查不是实时监控；对象变化后可重新检查，旧结论不能当作当前通过。'}

    def list(self):
        return [{'id': key, 'label': label, 'patch_origin': origin}
                for key, (_, label, origin) in self.projects.items()]

    def check(self, key):
        cfg, _, _ = self._entry(key)
        self.store.mkdir(parents=True, exist_ok=True)
        folder = self.store / uuid.uuid4().hex
        folder.mkdir()
        identity = _digest_tree(cfg.project_root)
        copy = folder / 'project'
        _copy_project(cfg.project_root, copy)
        copied_cfg = copy / cfg.config_path.relative_to(cfg.project_root)
        report = check_project(copied_cfg, output=folder / 'report.json', project_root=copy)
        self.results[key] = {'input_identity': identity, 'report': report, 'folder': folder}
        result = self.describe(key)
        result['operation'] = 'NEW_ISOLATED_CHECK_NO_MODEL'
        return result

    def export(self, key):
        cfg, _, _ = self._entry(key)
        self.store.mkdir(parents=True, exist_ok=True)
        folder = self.store / ('export-' + uuid.uuid4().hex)
        folder.mkdir()
        target = folder / 'tests/credproof-regression'
        export_regression_tests(cfg.config_path, target)
        (folder / 'export-instructions.txt').write_text(
            'Copy tests/credproof-regression into your authorized project. Keep credproof.toml in the root.\n'
            'Declare the wrapper path in project.optional_tests and register the credproof_safety marker.\n'
            'Run python -m pytest -q tests/credproof-regression; this executes a new isolated check, not a saved PASS.\n'
            'Requires pytest and prepared WSL/bubblewrap runtime; no model is needed.\n', encoding='utf-8')
        (folder / 'selected-scope.json').write_text(json.dumps(cfg.to_public_dict(), ensure_ascii=False, indent=2), 'utf-8')
        archive = folder / 'exported-tests.zip'
        with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as out:
            for file in sorted(folder.rglob('*')):
                if file.is_file() and file != archive:
                    out.write(file, file.relative_to(folder).as_posix())
        return archive
