"""Project intake for the local workbench: receive, inspect, configure.

Nothing here imports or executes project code.  Uploaded archives are unpacked
into a private folder under ``runs/intake`` with strict limits; detection uses
``ast`` only.  A configuration draft is validated by the same
``credproof_safety.config.load_config`` the checker uses.  Starting a review
copies the source, writes the frozen ``credproof.toml`` and hands the copy to
``ReviewWorkspace.open_project``; from then on only the entry file may change.
"""
from __future__ import annotations

import ast
from datetime import datetime, timezone
import io
import json
import re
import shutil
import stat
from pathlib import Path, PurePosixPath
import uuid
import zipfile

from credproof_safety.config import load_config
from credproof_safety.project import _copy_project, _digest_tree

LIMITS = {'upload_bytes': 16 * 1024 * 1024, 'files': 2000, 'file_bytes': 4 * 1024 * 1024,
          'expanded_bytes': 64 * 1024 * 1024}
IGNORED_PARTS = {'.git', '.venv', 'venv', '__pycache__', '.credproof', '__MACOSX', 'node_modules',
                 '.mypy_cache', '.pytest_cache', '.tox', '.idea', '.vscode'}
PLACEHOLDERS = {
    '__CREDPROOF_ALLOWED_FILE__': '允许目录中的资料文件（检查时自动生成）',
    '__CREDPROOF_FORBIDDEN_FILE__': '禁止目录中的文件，里面是本次的合成凭据',
    '__CREDPROOF_ALLOWED_URL__': '允许的模拟服务地址（检查时分配端口）',
    '__CREDPROOF_REDIRECT_URL__': '允许服务上会返回 302、跳往禁止服务的地址',
    '__CREDPROOF_FORBIDDEN_URL__': '禁止的模拟服务地址',
}
EXAMPLES_ROOT = 'examples'
_ID = re.compile(r'[0-9a-f]{32}\Z')
_NAME = re.compile(r'[A-Za-z][A-Za-z0-9_-]{0,63}\Z')
_IDENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\Z')
_ENV = re.compile(r'[A-Z][A-Z0-9_]{1,63}\Z')
_DIR = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z')
_SECRETISH = re.compile(r'TOKEN|KEY|SECRET|CREDENTIAL|PASSWORD|PASSWD|AUTH', re.I)


def now():
    return datetime.now(timezone.utc).isoformat()


class IntakeError(ValueError):
    """A request the user can fix; message is safe to show."""


def _write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


# ---------------------------------------------------------------- archives --

def _safe_member(name):
    if not isinstance(name, str) or not name or len(name) > 400:
        raise IntakeError('压缩包中有无效文件名。')
    if '\\' in name or ':' in name or name.startswith('/') or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise IntakeError(f'压缩包中有不安全的路径：{name[:80]}')
    parts = PurePosixPath(name).parts
    if any(part in ('..', '.', '') for part in parts) or len(parts) > 24:
        raise IntakeError(f'压缩包中有不安全的路径：{name[:80]}')
    return parts


def unpack_archive(data, destination):
    """Extract a zip under ``destination`` with the limits in LIMITS."""
    if not isinstance(data, (bytes, bytearray)) or not data:
        raise IntakeError('没有收到压缩包内容。')
    if len(data) > LIMITS['upload_bytes']:
        raise IntakeError('压缩包超过 16 MiB。')
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
        infos = archive.infolist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise IntakeError('无法读取压缩包，请上传 zip 格式。') from None
    if len(infos) > LIMITS['files'] * 3:
        raise IntakeError('压缩包条目过多。')
    accepted, total, seen = [], 0, set()
    for info in infos:
        parts = _safe_member(info.filename)
        if info.is_dir():
            continue
        if info.flag_bits & 0x1:
            raise IntakeError('不支持加密的压缩包。')
        mode = (info.external_attr >> 16) & 0o170000
        if mode == stat.S_IFLNK:
            raise IntakeError(f'压缩包中有符号链接：{info.filename[:80]}')
        if mode not in (0, stat.S_IFREG):
            raise IntakeError(f'压缩包中有特殊文件：{info.filename[:80]}')
        if any(part in IGNORED_PARTS for part in parts) or parts[-1].endswith('.pyc') or parts[-1] in ('.DS_Store', 'Thumbs.db'):
            continue
        if info.file_size > LIMITS['file_bytes']:
            raise IntakeError(f'单个文件超过 4 MiB：{info.filename[:80]}')
        total += info.file_size
        if total > LIMITS['expanded_bytes']:
            raise IntakeError('展开后超过 64 MiB。')
        folded = '/'.join(parts).casefold()
        if folded in seen:
            raise IntakeError(f'压缩包中有大小写冲突的重复文件：{info.filename[:80]}')
        seen.add(folded)
        accepted.append((info, parts))
        if len(accepted) > LIMITS['files']:
            raise IntakeError('文件数超过 2000 个。')
    if not accepted:
        raise IntakeError('压缩包里没有可用的文件。')
    tops = {parts[0] for _, parts in accepted}
    strip = 1 if len(tops) == 1 and all(len(parts) > 1 for _, parts in accepted) else 0
    destination.mkdir(parents=True)
    written = 0  # header sizes can lie; count the bytes actually expanded
    for info, parts in accepted:
        relative = parts[strip:]
        target = destination.joinpath(*relative)
        if not target.resolve().is_relative_to(destination.resolve()):
            raise IntakeError('压缩包路径越出目标目录。')
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open('xb') as output:
            remaining = LIMITS['file_bytes'] + 1
            while chunk := source.read(65536):
                remaining -= len(chunk)
                written += len(chunk)
                if remaining <= 0:
                    raise IntakeError(f'单个文件超过 4 MiB：{info.filename[:80]}')
                if written > LIMITS['expanded_bytes']:
                    raise IntakeError('展开后超过 64 MiB。')
                output.write(chunk)
    return destination


# --------------------------------------------------------------- detection --

def _files(root):
    rows = []
    for path in sorted(root.rglob('*')):
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if path.is_symlink():
            raise IntakeError('项目中有符号链接，当前版本不支持。')
        if path.is_file():
            rows.append({'path': relative.as_posix(), 'bytes': path.stat().st_size})
    return rows


def _module_name(relative):
    parts = PurePosixPath(relative).with_suffix('').parts
    if parts and parts[-1] == '__init__':
        parts = parts[:-1]
    if not parts or not all(_IDENT.fullmatch(p) for p in parts):
        return None
    return '.'.join(parts)


def _is_test(relative):
    parts = PurePosixPath(relative).parts
    return any(p in ('tests', 'test') for p in parts[:-1]) or parts[-1].startswith('test_') or parts[-1].endswith('_test.py') \
        or parts[-1] == 'conftest.py'


def detect(root):
    files = _files(root)
    python = [row['path'] for row in files if row['path'].endswith('.py')]
    tests = []
    for name in ('tests', 'test'):
        folder = root / name
        if folder.is_dir() and any(folder.rglob('test*.py')):
            tests.append(name)
    if not tests:
        tests = [p for p in python if '/' not in p and _is_test(p) and p != 'conftest.py']
    candidates, envs, parse_errors = [], {}, []
    for relative in python:
        if _is_test(relative) or len(PurePosixPath(relative).parts) > 3:
            continue
        try:
            tree = ast.parse((root / relative).read_text(encoding='utf-8'), filename=relative)
        except (SyntaxError, UnicodeDecodeError, ValueError):
            parse_errors.append(relative)
            continue
        module = _module_name(relative)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_') and module:
                params = len(node.args.posonlyargs) + len(node.args.args)
                if params >= 1 and not isinstance(node, ast.AsyncFunctionDef):
                    candidates.append({'module': module, 'callable': node.name, 'params': params, 'file': relative})
        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
                target = node.value
                if isinstance(target, ast.Attribute) and target.attr == 'environ':
                    name = node.slice.value
            elif isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant):
                func = node.func
                if isinstance(func, ast.Attribute) and (func.attr == 'getenv' or (
                        func.attr == 'get' and isinstance(func.value, ast.Attribute) and func.value.attr == 'environ')):
                    name = node.args[0].value
            if isinstance(name, str) and _ENV.fullmatch(name) and not name.startswith('CREDPROOF_ALLOWED') \
                    and not name.startswith('CREDPROOF_FORBIDDEN') and name not in ('CREDPROOF_CREDENTIAL_ENV', 'CREDPROOF_REDIRECT_URL'):
                envs[name] = envs.get(name, 0) + (3 if _SECRETISH.search(name) else 1)
    preferred = ('run', 'main', 'handle', 'process', 'execute')
    candidates.sort(key=lambda c: (c['callable'] not in preferred, '/' in c['file'], c['file'] != 'tool.py',
                                   preferred.index(c['callable']) if c['callable'] in preferred else 99, c['file'], c['callable']))
    env_rank = sorted(envs, key=lambda n: (-envs[n], n))
    return {'python_files': python, 'test_paths': tests, 'entry_candidates': candidates[:30],
            'credential_env_candidates': [n for n in env_rank if _SECRETISH.search(n)][:10],
            'unparsed_files': parse_errors[:20], 'file_count': len(files)}


# ------------------------------------------------------------ configuration --

def _toml_string(value):
    return json.dumps(value, ensure_ascii=False)


def _toml_key(key):
    return key if re.fullmatch(r'[A-Za-z0-9_-]+', key) else _toml_string(key)


def _toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, list):
        return '[' + ', '.join(_toml_value(v) for v in value) + ']'
    if isinstance(value, dict):
        return '{ ' + ', '.join(f'{_toml_key(k)} = {_toml_value(v)}' for k, v in value.items()) + ' }' if value else '{}'
    raise IntakeError('请求参数只能包含字符串、数字、布尔、数组和对象。')


def _request(value, where, depth=0):
    if depth > 4:
        raise IntakeError(f'{where} 嵌套过深（最多 4 层）。')
    if isinstance(value, dict):
        if len(value) > 32:
            raise IntakeError(f'{where} 键过多。')
        out = {}
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 64:
                raise IntakeError(f'{where} 中有无效的键。')
            out[key] = _request(item, where, depth + 1)
        return out
    if isinstance(value, list):
        if len(value) > 32:
            raise IntakeError(f'{where} 数组过长。')
        return [_request(item, where, depth + 1) for item in value]
    if isinstance(value, bool) or isinstance(value, (int, float)) or isinstance(value, str):
        if isinstance(value, str) and len(value) > 512:
            raise IntakeError(f'{where} 中的字符串过长。')
        if isinstance(value, float) and value != value:
            raise IntakeError(f'{where} 中有无效数字。')
        return value
    raise IntakeError(f'{where} 只能包含字符串、数字、布尔、数组和对象（不支持 null）。')


def _paths(value, name, *, allow_empty=False, glob=False):
    if not isinstance(value, list) or (not value and not allow_empty) or len(value) > 16:
        raise IntakeError(f'{name} 需要 1–16 项。' if not allow_empty else f'{name} 最多 16 项。')
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item) > 200:
            raise IntakeError(f'{name} 中有空项或过长的路径。')
        item = item.strip().replace('\\', '/')
        if item.startswith('/') or '..' in PurePosixPath(item).parts or ':' in item or (not glob and any(c in item for c in '*?[')):
            raise IntakeError(f'{name} 中的路径必须留在项目内：{item}')
        out.append(item)
    return out


def normalise(form):
    """Validate the wizard's structured fields; return a clean copy."""
    if not isinstance(form, dict):
        raise IntakeError('配置必须是对象。')
    entry = form.get('entry')
    if not isinstance(entry, dict):
        raise IntakeError('缺少入口设置。')
    module, function = entry.get('module'), entry.get('callable')
    if not isinstance(module, str) or not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*', module or ''):
        raise IntakeError('入口模块名无效，例如 tool 或 package.tool。')
    if not isinstance(function, str) or not _IDENT.fullmatch(function or ''):
        raise IntakeError('入口函数名无效。')
    scenarios = entry.get('scenarios')
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 8:
        raise IntakeError('需要 1–8 个入口场景。')
    clean_scenarios, names = [], set()
    for index, row in enumerate(scenarios, 1):
        if not isinstance(row, dict):
            raise IntakeError(f'场景 {index} 无效。')
        name = row.get('name')
        if not isinstance(name, str) or not _NAME.fullmatch(name):
            raise IntakeError(f'场景 {index} 的名称只能用字母、数字、下划线和连字符，并以字母开头。')
        if name in names:
            raise IntakeError(f'场景名称重复：{name}')
        names.add(name)
        error = row.get('expected_error')
        if error in ('', None):
            error = None
        elif not isinstance(error, str) or not _IDENT.fullmatch(error):
            raise IntakeError(f'场景 {name} 的预期异常必须是异常类名，例如 ValueError。')
        request = _request(row.get('request', {}), f'场景 {name} 的请求参数')
        if not isinstance(request, dict):
            raise IntakeError(f'场景 {name} 的请求参数必须是对象。')
        if len(json.dumps(request, ensure_ascii=False)) > 4096:
            raise IntakeError(f'场景 {name} 的请求参数超过 4 KiB。')
        network = row.get('require_network', False)
        if not isinstance(network, bool):
            raise IntakeError(f'场景 {name} 的“必须发出请求”需要是布尔值。')
        clean_scenarios.append({'name': name, 'request': request, 'expected_error': error, 'require_network': network})
    allowed, forbidden = form.get('allowed_dir'), form.get('forbidden_dir')
    for label, value in (('允许目录', allowed), ('禁止目录', forbidden)):
        if not isinstance(value, str) or not _DIR.fullmatch(value):
            raise IntakeError(f'{label}名称只能用字母、数字、点、下划线和连字符。')
    if allowed == forbidden:
        raise IntakeError('允许目录和禁止目录不能相同。')
    service = form.get('service') if isinstance(form.get('service'), dict) else {}
    enabled = service.get('enabled', False)
    prefix = service.get('path_prefix', '/api')
    require_credential = service.get('require_credential', False)
    if not isinstance(enabled, bool) or not isinstance(require_credential, bool):
        raise IntakeError('服务设置无效。')
    if enabled and (not isinstance(prefix, str) or not re.fullmatch(r'/[A-Za-z0-9_./-]{0,63}', prefix) or '..' in prefix):
        raise IntakeError('服务路径前缀必须以 / 开头，例如 /api。')
    if require_credential and not enabled:
        raise IntakeError('要求带凭据认证时，必须启用允许的服务。')
    env = form.get('credential_env', 'CREDPROOF_TEST_CREDENTIAL')
    if not isinstance(env, str) or not _ENV.fullmatch(env):
        raise IntakeError('凭据变量名必须是大写字母、数字和下划线，例如 API_TOKEN。')
    timeout = form.get('timeout_seconds', 30)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 120:
        raise IntakeError('超时需要在 1–120 秒之间。')
    read_required = form.get('require_allowed_file_read', False)
    if not isinstance(read_required, bool):
        raise IntakeError('“必须实际读取允许资料”需要是布尔值。')
    return {'tests': _paths(form.get('tests'), '必要测试'),
            'optional_tests': _paths(form.get('optional_tests', []), '可选测试', allow_empty=True),
            'source_scope': _paths(form.get('source_scope', ['*.py', '**/*.py']), '源码范围', glob=True),
            'entry': {'module': module, 'callable': function, 'scenarios': clean_scenarios},
            'allowed_dir': allowed, 'forbidden_dir': forbidden,
            'require_allowed_file_read': read_required,
            'service': {'enabled': enabled, 'path_prefix': prefix if enabled else '/api',
                        'require_credential': require_credential},
            'credential_env': env, 'timeout_seconds': timeout}


def render_toml(form):
    entry_file = form['entry']['module'].replace('.', '/') + '.py'
    first = form['entry']['scenarios'][0]
    lines = ['# Generated by the CredProof workbench configuration wizard.',
             '# Only the entry file may change during review; tests and this file are frozen.',
             'schema = "credproof.project-safety/v1"', '', '[project]', 'root = "."',
             f'tests = {_toml_value(form["tests"])}',
             f'optional_tests = {_toml_value(form["optional_tests"])}',
             f'source_scope = {_toml_value(form["source_scope"])}',
             f'mutable_scope = {_toml_value([entry_file])}', '', '[files]',
             f'allowed_dirs = {_toml_value([form["allowed_dir"]])}',
             f'forbidden_dirs = {_toml_value([form["forbidden_dir"]])}',
             f'require_allowed_file_read = {_toml_value(form["require_allowed_file_read"])}', '', '[network]',
             f'require_service_credential = {_toml_value(form["service"]["require_credential"])}']
    if form['service']['enabled']:
        lines += ['allowed_services = [',
                  f'  {{ scheme = "http", host = "127.0.0.1", port = 0, path_prefix = {_toml_string(form["service"]["path_prefix"])} }},',
                  ']']
    else:
        lines.append('allowed_services = []')
    lines += ['', '[credentials]', f'env = {_toml_string(form["credential_env"])}', '', '[entry]',
              f'module = {_toml_string(form["entry"]["module"])}',
              f'callable = {_toml_string(form["entry"]["callable"])}']
    if first['expected_error']:
        lines.append(f'expected_error = {_toml_string(first["expected_error"])}')
    lines.append(f'request = {_toml_value(first["request"])}')
    for row in form['entry']['scenarios']:
        lines += ['', '[[entry.scenarios]]', f'name = {_toml_string(row["name"])}']
        if row['expected_error']:
            lines.append(f'expected_error = {_toml_string(row["expected_error"])}')
        if row['require_network']:
            lines.append('require_network = true')
        lines.append(f'request = {_toml_value(row["request"])}')
    lines += ['', '[limits]', f'timeout_seconds = {_toml_value(form["timeout_seconds"])}', 'report_dir = ".credproof"', '']
    return '\n'.join(lines)


def form_from_config(cfg):
    public = cfg.to_public_dict()
    service = public['services'][0] if public['services'] else None
    return {'tests': public['tests'], 'optional_tests': public['optional_tests'], 'source_scope': public['source_scope'],
            'entry': {'module': public['entry']['module'], 'callable': public['entry']['callable'],
                      'scenarios': [{'name': s['name'], 'request': s['request'], 'expected_error': s['expected_error'],
                                     'require_network': s['require_network']} for s in public['entry']['scenarios']]},
            'allowed_dir': public['allowed_dirs'][0], 'forbidden_dir': public['forbidden_dirs'][0],
            'require_allowed_file_read': public['require_allowed_file_read'],
            'service': {'enabled': service is not None, 'path_prefix': service['path_prefix'] if service else '/api',
                        'require_credential': public['require_service_credential']},
            'credential_env': public['credential_env'], 'timeout_seconds': public['timeout_seconds']}


def default_form(found):
    entry = (found['entry_candidates'] or [{'module': 'tool', 'callable': 'run'}])[0]
    env = (found['credential_env_candidates'] or ['CREDPROOF_TEST_CREDENTIAL'])[0]
    return {'tests': found['test_paths'][:1] or ['tests'], 'optional_tests': [], 'source_scope': ['*.py', '**/*.py'],
            'entry': {'module': entry['module'], 'callable': entry['callable'],
                      'scenarios': [{'name': 'normal', 'request': {}, 'expected_error': None, 'require_network': False}]},
            'allowed_dir': 'data', 'forbidden_dir': 'secrets', 'require_allowed_file_read': False,
            'service': {'enabled': False, 'path_prefix': '/api', 'require_credential': False},
            'credential_env': env, 'timeout_seconds': 30}


# -------------------------------------------------------------- workspace --

class IntakeWorkspace:
    def __init__(self, root, *, authorized=None):
        self.root = Path(root)
        self.store = self.root / 'runs/intake'
        self.authorized = dict(authorized or {})  # key -> (config_path, label)

    # Examples come from the installed checkout, never from a request path.
    def examples(self):
        rows = []
        assistant = self.root / EXAMPLES_ROOT / 'material_assistant'
        if (assistant / 'credproof.toml').is_file():
            rows.append({'id': 'material-assistant', 'label': '资料助手（问题版本）', 'kind': 'example',
                         'description': '首页真实案例的原始代码：越界读取、跟随跳转、凭据外流。'})
        bench = self.root / EXAMPLES_ROOT / 'bench'
        for folder in sorted(bench.iterdir()) if bench.is_dir() else ():
            meta_path = folder / 'meta.json'
            if not (folder / 'project/credproof.toml').is_file() or not meta_path.is_file():
                continue
            try:
                meta = _read_json(meta_path)
                rows.append({'id': 'bench-' + meta['id'], 'label': f'{meta["title"]["zh"]}（对照评测目标）', 'kind': 'example',
                             'description': meta['flaw']['zh'] + '。业务测试' + ('能' if meta.get('business_tests_detect_flaw') else '不能') + '发现这处缺陷。'})
            except (OSError, ValueError, KeyError, TypeError):
                continue
        for key, (_, label) in self.authorized.items():
            rows.append({'id': 'authorized-' + key, 'label': label, 'kind': 'authorized',
                         'description': '启动时由本机操作者用 --project-config 授权的项目。'})
        return rows

    def _example_source(self, example_id):
        if example_id == 'material-assistant':
            return self.root / EXAMPLES_ROOT / 'material_assistant', '资料助手（问题版本）'
        if isinstance(example_id, str) and example_id.startswith('bench-'):
            for row in self.examples():
                if row['id'] == example_id:
                    folder = self.root / EXAMPLES_ROOT / 'bench' / example_id[len('bench-'):] / 'project'
                    return folder, row['label']
        if isinstance(example_id, str) and example_id.startswith('authorized-') and example_id[11:] in self.authorized:
            path, label = self.authorized[example_id[11:]]
            cfg = load_config(path)
            if Path(cfg.config_path).parent != Path(cfg.project_root):
                raise IntakeError('授权项目的 credproof.toml 需要放在项目根目录。')
            return Path(cfg.project_root), label
        raise IntakeError('没有这个示例项目。')

    def _new(self, source_kind, label):
        identifier = uuid.uuid4().hex
        folder = self.store / identifier
        folder.mkdir(parents=True)
        return identifier, folder

    def _finish(self, identifier, folder, source_kind, label):
        source = folder / 'source'
        found = detect(source)
        existing = {'present': (source / 'credproof.toml').is_file(), 'valid': False, 'error': None}
        form, toml, origin = None, None, 'form'
        if existing['present']:
            try:
                cfg = load_config(source / 'credproof.toml', project_root=source)
                form = form_from_config(cfg)
                toml = (source / 'credproof.toml').read_text(encoding='utf-8')
                existing['valid'], origin = True, 'existing'
            except (OSError, ValueError) as error:
                existing['error'] = str(error)[:300]
        if form is None:
            form = default_form(found)
            toml = render_toml(form)
        found['existing_config'] = existing
        _write_json(folder / 'intake.json', {'id': identifier, 'label': label, 'source': source_kind,
                    'created_at': now(), 'status': 'DRAFT', 'review_id': None,
                    'tree_sha256': _digest_tree(source), 'detected': found})
        self._save_draft(folder, form, toml, origin)
        return self.view(identifier)

    def from_upload(self, data, label=None):
        label = (label or '上传的项目').strip()[:80] or '上传的项目'
        identifier, folder = self._new('upload', label)
        try:
            unpack_archive(data, folder / 'source')
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return self._finish(identifier, folder, 'upload', label)

    def from_example(self, example_id):
        source, label = self._example_source(example_id)
        identifier, folder = self._new('example', label)
        try:
            _copy_project(source, folder / 'source')
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return self._finish(identifier, folder, 'authorized' if example_id.startswith('authorized-') else 'example', label)

    def folder(self, identifier):
        if not isinstance(identifier, str) or not _ID.fullmatch(identifier):
            raise IntakeError('没有这个接入记录。')
        folder = self.store / identifier
        if folder.is_symlink() or not (folder / 'intake.json').is_file():
            raise IntakeError('没有这个接入记录。')
        return folder

    def _save_draft(self, folder, form, toml, origin):
        draft_dir = folder / 'source/.credproof'
        draft_dir.mkdir(exist_ok=True)
        draft = draft_dir / 'draft-credproof.toml'
        draft.write_text(toml, encoding='utf-8', newline='\n')
        errors, warnings = [], []
        try:
            cfg = load_config(draft, project_root=folder / 'source')
            entry = cfg.entry.module.replace('.', '/') + '.py'
            source = folder / 'source'
            if not (source / entry).is_file():
                errors.append(f'入口文件 {entry} 不存在。')
            elif not cfg.matches_source(entry):
                errors.append(f'入口文件 {entry} 不在源码范围内。')
            else:
                try:
                    tree = ast.parse((source / entry).read_text(encoding='utf-8'))
                    names = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
                    names |= {t.id for n in tree.body if isinstance(n, ast.Assign) for t in n.targets if isinstance(t, ast.Name)}
                    if cfg.entry.callable not in names:
                        warnings.append(f'在 {entry} 顶层没有找到 {cfg.entry.callable}。')
                except (SyntaxError, UnicodeDecodeError, ValueError):
                    warnings.append(f'{entry} 无法静态解析，检查时可能报错。')
            for name in cfg.tests:
                path = source / name
                if not path.exists():
                    errors.append(f'必要测试路径 {name} 不存在。')
                elif path.is_dir() and not any(path.rglob('test*.py')) and not any(path.rglob('*_test.py')):
                    warnings.append(f'必要测试路径 {name} 下没有 test_*.py。')
            env_used = cfg.credential_env in (source / entry).read_text(encoding='utf-8', errors='replace') if (source / entry).is_file() else False
            if not env_used:
                warnings.append(f'入口文件里没有出现凭据变量名 {cfg.credential_env}；如果工具从别处读取凭据，可以忽略。')
            if cfg.require_service_credential and not cfg.services:
                errors.append('要求带凭据认证时必须启用允许的服务。')
            if all(not s.request for s in cfg.entry.scenarios):
                warnings.append('所有场景的请求参数都是空的；请按入口函数的真实参数填写。')
        except (OSError, ValueError) as error:
            errors.append(str(error)[:300])
        _write_json(folder / 'draft.json', {'form': form, 'origin': origin, 'errors': errors, 'warnings': warnings,
                                            'saved_at': now()})

    def view(self, identifier):
        folder = self.folder(identifier)
        record = _read_json(folder / 'intake.json')
        draft = _read_json(folder / 'draft.json')
        files = _files(folder / 'source')
        return {'schema': 'credproof.intake/v1', 'id': identifier, 'label': record['label'],
                'source': record['source'], 'created_at': record['created_at'], 'status': record['status'],
                'review_id': record['review_id'], 'tree_sha256': record['tree_sha256'],
                'files': files[:400], 'files_truncated': len(files) > 400, 'file_count': len(files),
                'detected': record['detected'], 'config': draft['form'], 'config_origin': draft['origin'],
                'toml': (folder / 'source/.credproof/draft-credproof.toml').read_text(encoding='utf-8'),
                'valid': not draft['errors'], 'errors': draft['errors'], 'warnings': draft['warnings'],
                'placeholders': PLACEHOLDERS, 'limits': LIMITS}

    def list(self):
        rows = []
        if not self.store.is_dir():
            return rows
        for path in sorted(self.store.glob('*/intake.json')):
            if path.parent.is_symlink() or not _ID.fullmatch(path.parent.name):
                continue
            try:
                record = _read_json(path)
                draft = _read_json(path.parent / 'draft.json')
            except (OSError, ValueError):
                continue
            rows.append({'id': path.parent.name, 'label': record.get('label'), 'source': record.get('source'),
                         'status': record.get('status'), 'created_at': record.get('created_at'),
                         'review_id': record.get('review_id'), 'valid': not draft.get('errors')})
        rows.sort(key=lambda r: r.get('created_at') or '', reverse=True)
        return rows[:200]

    def save_config(self, identifier, form):
        folder = self.folder(identifier)
        if _read_json(folder / 'intake.json')['status'] != 'DRAFT':
            raise IntakeError('配置已经冻结；要换配置，请重新接入项目。')
        clean = normalise(form)
        self._save_draft(folder, clean, render_toml(clean), 'form')
        return self.view(identifier)

    def start(self, identifier, reviews, label=None):
        folder = self.folder(identifier)
        record = _read_json(folder / 'intake.json')
        if record['status'] != 'DRAFT':
            raise IntakeError('这个接入记录已经开始审阅。')
        state = self.view(identifier)
        if not state['valid']:
            raise IntakeError('配置还有错误，不能开始。')
        if _digest_tree(folder / 'source') != record['tree_sha256']:
            raise IntakeError('接入的源副本发生了变化，请重新接入。')
        if label is not None and (not isinstance(label, str) or len(label) > 80):
            raise IntakeError('显示名最多 80 字。')
        staged = folder / ('staged-' + uuid.uuid4().hex)
        _copy_project(folder / 'source', staged)
        (staged / 'credproof.toml').write_text(state['toml'], encoding='utf-8', newline='\n')
        try:
            review = reviews.open_project(staged, 'intake-' + identifier, (label or record['label']).strip() or record['label'])
        finally:
            shutil.rmtree(staged, ignore_errors=True)
        record.update(status='STARTED', review_id=review['id'], started_at=now())
        _write_json(folder / 'intake.json', record)
        return {'intake': self.view(identifier), 'review': review}
