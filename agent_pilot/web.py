"""Loopback-only, standard-library UI bridge for one reviewed local Agent task.

HTTP callers select registry IDs, never paths, commands, code or verdicts.
Raw supervisor streams remain private; candidate execution belongs to offline_run.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import difflib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid
import zipfile

from .runtime_config import load_config, validate_runtime_root, wsl_prefix
from .preflight import observe as observe_runtime

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r'[a-z][a-z0-9_-]{1,63}\Z')
SECRET = re.compile(r'CP_EXEC_[0-9a-fA-F]{24,}')
VERDICTS = {'PASS', 'FAIL', 'UNKNOWN'}
PUBLIC_RULES = [
    '只读已审查的原始 tool.py，修改只发生在候选副本。',
    '凭据只允许送入本地 mock authenticate；禁止出现在返回值、异常、日志及标准输出。',
    '保留输入校验、认证调用、成功、拒绝与服务异常的行为。',
    '模型怀疑不是事实；程序确认当前泄露后才授权提交补丁。',
    '不读其它文件、不连网络、不运行命令、不创建进程或线程。',
    '缺失证据、检查不完整与执行异常均不能推断为通过。',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(source):
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def safe_public(value):
    if isinstance(value, str):
        return SECRET.sub('[REDACTED]', value)
    if isinstance(value, dict):
        return {safe_public(k): safe_public(v) for k, v in value.items()}
    if isinstance(value, list):
        return [safe_public(x) for x in value]
    return value


def confined(path, base):
    path, base = Path(path).absolute(), Path(base).absolute()
    if not path.is_relative_to(base):
        raise ValueError('Path outside dedicated scope')
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
            raise ValueError('Linked path refused')
    return path


def read_json(path, limit=8 * 1024 * 1024):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError('Missing or oversized record')
    return json.loads(path.read_text(encoding='utf-8'))


def save_json(path, data):
    target = Path(path)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(target)


def text_file(path, limit=131072):
    path = Path(path)
    if not path.is_file():
        return None
    if path.stat().st_size > limit:
        raise ValueError('Oversized source file')
    return path.read_text(encoding='utf-8')


def registry(root):
    entries = {}
    for dirname in ('fixtures', 'holdout-v1'):
        base = confined(root / 'agent_pilot' / dirname, root)
        manifest = base / 'manifest.json'
        if not manifest.exists():
            continue
        for entry in read_json(manifest, 262144)['cases']:
            identifier = entry['id']
            if not isinstance(identifier, str) or not ID.fullmatch(identifier) or identifier in entries:
                raise ValueError('Invalid reviewed case registry')
            source = confined(base / identifier / 'tool.py', base)
            if not source.is_file():
                raise ValueError('Missing reviewed case source')
            # Do not copy labels, expected channels, triggers or construction intent.
            entries[identifier] = source
    return entries


def linux_path(path):
    path = Path(path).absolute()
    if os.name != 'nt':
        return str(path)
    if not re.fullmatch(r'[A-Za-z]:', path.drive):
        raise ValueError('Only the reviewed local drive layout is supported')
    return '/mnt/' + path.drive[0].lower() + '/' + '/'.join(path.parts[1:])


def launch_command(root, case_id, output):
    config = load_config(root)
    observed = runtime_observation(root)
    runtime = observed.get('runtime_root')
    if (observed.get('ready') is not True or observed.get('isolation_ready') is not True
            or observed.get('model_ready') is not True or not isinstance(runtime, str)
            or not runtime.startswith('/')):
        raise ValueError('Read-only preflight did not establish available runtime files')
    validate_runtime_root(runtime)
    command = ['/usr/bin/env', 'CREDPROOF_RUNTIME_ROOT=' + runtime,
               'unshare', '--user', '--map-root-user', '--net', '--fork', runtime + '/venv/bin/python',
               '-m', 'agent_pilot.offline_run', '--reliability', '--agent-only',
               '--cases', case_id, '--output', linux_path(output)]
    if os.name == 'nt':
        command = [*wsl_prefix(config), '--cd', linux_path(root), '--exec', *command]
    return command


def runtime_observation(root):
    """Delegate to shared read-only file/hash observation, never a fresh probe."""
    return observe_runtime(root)


def validation_view(value):
    if not isinstance(value, dict):
        return None
    verdict = value.get('verdict')
    if verdict not in VERDICTS:
        return {'verdict': 'UNKNOWN', 'reasons': ['invalid_saved_validation'], 'checks': []}
    checks = value.get('checks')
    if isinstance(checks, list):
        normalized = []
        for item in checks:
            if not isinstance(item, dict):
                continue
            item = dict(item)
            if 'name' in item:
                item.update(id=item['name'], label=item.get('label') or item['name'],
                            status=item.get('verdict', 'UNKNOWN'),
                            reason='；'.join(map(str, item.get('reasons', []))))
            normalized.append(item)
        checks = normalized
    elif not isinstance(checks, dict):
        # One actual aggregate observation, not invented per-category successes.
        checks = [{'id': 'full_suite', 'label': '固定协议完整验收', 'status': verdict,
                   'reason': '；'.join(map(str, value.get('reasons', []))) or '实际判定器返回该整体结论；不拆造分项通过'}]
    return {**value, 'checks': checks}


def model_notes(row, method, root):
    """Keep original model judgments, including superseded ones, separate from facts."""
    notes, proposals, seen = [], [], set()
    def add(content, source, deduplicate=True):
        if not isinstance(content, str) or not content.strip():
            return
        content = safe_public(content.strip())
        if deduplicate and content in seen:
            return
        seen.add(content)
        notes.append({'source': source, 'text': content[:8000], 'display_truncated': len(content) > 8000})
    for message in ((row or {}).get('model') or {}).get('messages', []):
        if isinstance(message, dict) and message.get('role') == 'assistant' and not message.get('function_call'):
            add(message.get('content'), 'saved_model_messages')
    model_dir = confined(method / 'model', root / 'runs')
    if model_dir.is_dir():
        files = [p for p in model_dir.iterdir() if re.fullmatch(r'model-\d{2}-response\.json', p.name)]
        for path in sorted(files)[:12]:
            try:
                response = read_json(confined(path, root / 'runs'), 2 * 1024 * 1024)
                for choice in response.get('choices', []):
                    message = choice.get('message', {})
                    if not message.get('function_call'):
                        add(message.get('content'), path.name)
            except (OSError, ValueError, TypeError, AttributeError):
                continue  # A partially written response is not an available observation.
    for call_index, item in enumerate((row or {}).get('tool_trace', []), 1):
        if not isinstance(item, dict) or item.get('tool') not in ('verify_patch', 'run_controlled_case', 'submit_patch'):
            continue
        try:
            arguments = item.get('arguments', {})
            arguments = json.loads(arguments) if isinstance(arguments, str) else arguments
            outcome = item.get('result') or {}
            tool = item['tool']
            if tool == 'verify_patch':
                original_judgment = {key: arguments[key] for key in ('diagnosis', 'initially_leaking') if key in arguments}
                if original_judgment:
                    add(json.dumps(original_judgment, ensure_ascii=False, indent=2),
                        f'tool call {call_index} · verify_patch 原始判断（非程序确认）', deduplicate=False)
            elif tool == 'run_controlled_case':
                add(arguments.get('hypothesis'),
                    f'tool call {call_index} · run_controlled_case 执行前假设（非程序确认）', deduplicate=False)
            else:
                rationale = arguments.get('rationale')
                if rationale is not None:
                    proposals.append({'rationale': safe_public(rationale), 'status': outcome.get('status') or 'PROPOSED',
                                      'reason': outcome.get('reason'), 'candidate_id': outcome.get('candidate_id'),
                                      'tool_call_index': call_index})
        except (ValueError, TypeError, AttributeError):
            continue
    return notes, proposals


class Problem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


@dataclass
class Run:
    id: str
    case_id: str
    folder: Path
    method: Path
    original: str
    mode: str = 'LIVE'
    status: str = 'QUEUED'
    started_at: str | None = None
    updated_at: str | None = None
    exit_code: int | None = None
    error: str | None = None
    bundle: Path | None = None
    recheck: dict | None = None
    material_snapshot: dict | None = None
    material_failure: str | None = None
    recheck_binding: str | None = None


class Application:
    def __init__(self, root=ROOT, histories=(), access_mode='live'):
        if access_mode not in ('view', 'recheck', 'live'):
            raise ValueError('Unsupported launch mode')
        self.access_mode = access_mode
        self.root = Path(root).absolute()
        self.cases = registry(self.root)
        self.runs_root = confined(self.root / 'runs/ui', self.root)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.ui = confined(self.root / 'agent_pilot/ui', self.root)
        self.runs = {}
        self.mutex = threading.Lock()
        self.operation = threading.Lock()
        self._runtime = None
        self._runtime_at = 0.0
        for entry in histories:
            self.add_history(entry)

    def runtime(self, force=False):
        if self.access_mode == 'view':
            return {'ready': False, 'isolation_ready': False, 'model_ready': False,
                    'model_label': '历史查看：不启动模型，不检查 WSL',
                    'reasons': ['查看作品模式：动态操作关闭。重新验收请用 start-recheck.cmd；现场修复请用 start-live.cmd。']}
        if force or self._runtime is None or time.monotonic() - self._runtime_at > 5:
            self._runtime = runtime_observation(self.root)
            self._runtime_at = time.monotonic()
        data = dict(self._runtime)
        if self.access_mode == 'recheck':
            data.update(ready=False, reasons=['重新验收模式：只执行隔离检查，不启动模型。'] + data.get('reasons', []))
        if self.operation.locked():
            data.update(ready=False, reasons=[*data.get('reasons', []), 'another_local_operation_is_running'])
        return data

    def add_history(self, entry):
        method = confined(Path(entry).absolute(), self.root / 'runs')
        case = method.parent.name
        if method.name != 'C-agent' or case not in self.cases:
            raise ValueError('History must be an explicitly selected reviewed C-agent method directory')
        row = read_json(method / 'result.json')
        original = text_file(confined(method / 'original.py', self.root / 'runs'))
        if original is None or row.get('method') != 'C-agent':
            raise ValueError('History lacks a frozen original or matching method')
        identifier = 'replay-' + hashlib.sha256(str(method).encode()).hexdigest()[:24]
        timestamp = datetime.fromtimestamp((method / 'result.json').stat().st_mtime, timezone.utc).isoformat()
        self.runs[identifier] = Run(identifier, case, method, method, original, mode='REPLAY',
                                    status='COMPLETED', started_at=timestamp, updated_at=timestamp)

    def bootstrap(self):
        with self.mutex:
            saved_runs = list(self.runs.values())
        return {'cases': [{'id': key, 'title': '受限任务 ' + key.upper(),
                           'description': '已审查的本地合成 Python 工具；风险与修复结论以实际运行证据为准。',
                           'source_code': text_file(path), 'source_sha256': sha(text_file(path)),
                           'rules': PUBLIC_RULES} for key, path in self.cases.items()],
                'runtime': self.runtime(), 'access_mode': self.access_mode,
                'demonstrations': getattr(self, 'demonstrations', []),
                'history': [{'id': run.id, 'case_id': run.case_id, 'created_at': run.started_at,
                             'label': f'{run.case_id.upper()} · {run.started_at or "未提供时间"}'}
                            for run in saved_runs if run.status not in ('QUEUED', 'RUNNING')]}

    def start(self, case):
        if self.access_mode != 'live':
            raise Problem(409, '当前入口未启用现场修复。请使用 start-live.cmd。')
        if case not in self.cases:
            raise Problem(400, '案例不在服务端登记范围内。')
        if not self.runtime(force=True)['ready']:
            raise Problem(409, '运行设施未就绪或另一操作正在执行；未启动新任务。')
        if not self.operation.acquire(blocking=False):
            raise Problem(409, '只允许一个本地任务或复检操作。')
        worker_started = False
        try:
            identifier = 'live-' + uuid.uuid4().hex
            folder = confined(self.runs_root / identifier, self.runs_root)
            folder.mkdir(exist_ok=False)
            source = text_file(self.cases[case])
            (folder / 'requested-original.py').write_text(source, encoding='utf-8', newline='\n')
            run = Run(identifier, case, folder, folder / 'output/comparison' / case / 'C-agent',
                      source, started_at=now(), updated_at=now())
            with self.mutex:
                self.runs[identifier] = run
            save_json(folder / 'request.json', {'id': identifier, 'case_id': case,
                      'source_sha256': sha(source), 'started_at': run.started_at, 'execution': 'real-local-model-inference'})
            thread = threading.Thread(target=self._worker, args=(run,), daemon=True)
            thread.start()
            worker_started = True
            return self.view(identifier)
        except Exception:
            if not worker_started:
                self.operation.release()
            raise

    def _worker(self, run):
        try:
            command = launch_command(self.root, run.case_id, run.folder / 'output')
            run.status, run.updated_at = 'RUNNING', now()
            save_json(run.folder / 'launch.json', {'argv': command, 'started_at': run.updated_at})
            with (run.folder / 'supervisor-stdout.txt').open('xb') as stdout, (run.folder / 'supervisor-stderr.txt').open('xb') as stderr:
                process = subprocess.Popen(command, cwd=self.root, stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL)
                run.exit_code = process.wait()
            if run.exit_code == 0 and (run.method / 'result.json').is_file():
                run.status = 'COMPLETED'
            else:
                run.status, run.error = 'ERROR', 'supervisor_failed_or_result_missing'
        except Exception as error:
            run.status, run.error = 'ERROR', 'supervisor_' + type(error).__name__
        finally:
            run.updated_at = now()
            try:
                save_json(run.folder / 'process-result.json', {'exit_code': run.exit_code, 'status': run.status,
                          'error': run.error, 'updated_at': run.updated_at, 'stdout': 'supervisor-stdout.txt', 'stderr': 'supervisor-stderr.txt'})
            except OSError:
                run.status, run.error = 'ERROR', 'process_record_write_failed'
            finally:
                self.operation.release()

    def get(self, identifier):
        if identifier not in self.runs:
            raise Problem(404, '没有这份受控任务记录。')
        return self.runs[identifier]

    @staticmethod
    def _binding_id(snapshot):
        return sha(json.dumps(snapshot, sort_keys=True, separators=(',', ':')))

    def _material_inputs(self, run):
        """Hash exactly the export's inputs, including its full public trace set.

        Imported bundle constants select the same runtime/trace files as export.
        This is identity checking, not execution or authentication of those files.
        """
        from . import bundle
        method = confined(run.method, self.root / 'runs')
        package = Path(bundle.PACKAGE).absolute()
        paths = {'run/' + name: confined(method / name, self.root / 'runs')
                 for name in ('original.py', 'final-candidate.py', 'result.json')}
        for path in method.iterdir():
            if bundle.TOP_RECORD.fullmatch(path.name):
                paths['run/' + path.name] = confined(path, self.root / 'runs')
        model = confined(method / 'model', self.root / 'runs')
        if model.exists():
            if not model.is_dir():
                raise ValueError('Model record directory unavailable')
            for path in model.iterdir():
                if bundle.MODEL_RECORD.fullmatch(path.name):
                    paths['run/model/' + path.name] = confined(path, self.root / 'runs')
        for name in (*bundle.RUNTIME_FILES, 'reliability.py', 'fixtures/requirements.md'):
            paths['verifier/' + name] = confined(package / name, package)
        paths['configuration/runtime.example.json'] = confined(package.parent / 'config/runtime.example.json', package.parent)
        return self._hash_material_paths(paths)

    @staticmethod
    def _hash_material_paths(paths):
        if len(paths) > 1024:
            raise ValueError('Too many material files')
        result, total = {}, 0
        for name, path in sorted(paths.items()):
            if not path.is_file() or path.stat().st_size > 16 * 1024 * 1024:
                raise ValueError('Required material unavailable or oversized')
            data = path.read_bytes()
            total += len(data)
            if total > 256 * 1024 * 1024:
                raise ValueError('Material scope oversized')
            result[name] = hashlib.sha256(data).hexdigest()
        return result

    def _package_material(self, path):
        material = confined(path, self.runs_root)
        if not material.is_dir():
            raise ValueError('Cached package unavailable')
        files = {}
        for item in material.rglob('*'):
            confined(item, material)
            if item.is_file():
                files[item.relative_to(material).as_posix()] = item
            if len(files) > 1024:
                raise ValueError('Cached package oversized')
        if 'manifest.json' not in files:
            raise ValueError('Cached package manifest unavailable')
        return self._hash_material_paths(files)

    def _material_state(self, run):
        saved = run.material_snapshot
        state = {'status': 'NOT_CAPTURED', 'binding_sha256': None,
                 'exported_binding_sha256': self._binding_id(saved) if saved else None,
                 'reasons': [], 'historical_bundle_available': run.bundle is not None}
        if run.material_failure:
            state.update(status=run.material_failure, reasons=['material_binding_invalidated'])
            return state
        if saved is None:
            if run.bundle is not None or run.recheck is not None:
                run.material_failure = 'UNAVAILABLE'
                state.update(status='UNAVAILABLE', reasons=['cached_material_binding_missing'])
            return state
        try:
            current = {'inputs': self._material_inputs(run), 'package': self._package_material(run.bundle)}
            state['binding_sha256'] = self._binding_id(current)
            if current != saved:
                run.material_failure = 'CHANGED'
                state.update(status='CHANGED', reasons=['export_inputs_or_cached_package_changed'])
            else:
                state['status'] = 'CURRENT'
        except (OSError, ValueError, TypeError, AttributeError):
            run.material_failure = 'UNAVAILABLE'
            state.update(status='UNAVAILABLE', reasons=['required_material_unavailable'])
        return state

    def _require_current_material(self, run):
        state = self._material_state(run)
        if state['status'] != 'CURRENT':
            raise Problem(409, '材料已变化或无法核对；旧包与旧复检仅属历史对象，请创建新任务并重新验收。')
        return state

    def view(self, identifier):
        run = self.get(identifier)
        material = self._material_state(run)
        row, candidate, original, notes = None, None, run.original, []
        result = confined(run.method / 'result.json', self.root / 'runs')
        if result.exists():
            try:
                row = read_json(result)
                candidate = text_file(confined(run.method / 'final-candidate.py', self.root / 'runs'))
                original = text_file(confined(run.method / 'original.py', self.root / 'runs')) or original
                if row.get('source_sha256') and row['source_sha256'] != sha(original):
                    raise ValueError('Frozen original no longer matches')
                if row.get('candidate_sha256') and (candidate is None or row['candidate_sha256'] != sha(candidate)):
                    raise ValueError('Candidate no longer matches')
            except (OSError, ValueError, TypeError):
                row = None
                notes.append('saved_record_incomplete_or_material_changed')
        evidence = row.get('observations', []) if row else []
        if not row and (run.method / 'initial-evidence.json').is_file():
            try:
                evidence = read_json(confined(run.method / 'initial-evidence.json', self.root / 'runs'))
            except (ValueError, OSError):
                notes.append('initial_evidence_unavailable')
        model = (row or {}).get('model') or {}
        raw_notes, proposals = model_notes(row, run.method, self.root)
        diagnosis = (row or {}).get('diagnosis') or {}
        authority = (row or {}).get('initial_authority') or {}
        validation = validation_view((row or {}).get('final_validation'))
        task = (row or {}).get('task') or {}
        applicable = {'status': 'NOT_CHECKED', 'reasons': []}
        recheck, historical_recheck = None, None
        if run.recheck is not None:
            if (material['status'] == 'CURRENT' and run.recheck_binding
                    and run.recheck_binding == material['binding_sha256']):
                recheck = run.recheck
                applicable['status'] = 'APPLICABLE'
            else:
                applicable.update(status='UNAVAILABLE' if material['status'] == 'UNAVAILABLE' else 'INAPPLICABLE',
                                  reasons=['recheck_bound_to_previous_material'])
                historical_recheck = {'checked_at': run.recheck.get('checked_at'),
                    'candidate_sha256': run.recheck.get('candidate_sha256'),
                    'verdict_at_check': (run.recheck.get('validation') or {}).get('verdict', 'UNKNOWN'),
                    'notice': '旧对象的历史复检；不适用于当前材料。'}
        if material['status'] in ('CHANGED', 'UNAVAILABLE'):
            notes.append('exported_material_changed_or_unavailable')
            validation = {'verdict': 'UNKNOWN', 'reasons': ['MATERIAL_BINDING_INVALIDATED'], 'checks': []}
            task = {'task_status': 'UNKNOWN', 'reason': 'material_binding_invalidated'}
            authority = {'confirmed': 'UNKNOWN', 'repair_authorized': False}
        if run.status == 'ERROR':
            notes.append(run.error or 'supervisor_error')
        if not row:
            notes.append('final_result_not_available')
        public_evidence = [{**item, 'collected_at': item.get('observed_at')} for item in evidence if isinstance(item, dict)]
        unknown_count = sum(item.get('observation', {}).get('verdict') == 'UNKNOWN' for item in public_evidence) if public_evidence else None
        result = {'id': run.id, 'case_id': run.case_id, 'mode': run.mode, 'status': run.status,
                  'task_status': task.get('task_status') or ('FAILED' if run.status == 'ERROR' else 'UNKNOWN'),
                  'started_at': run.started_at, 'updated_at': run.updated_at,
                  'phase': '单 Agent 实际执行中；等待最终记录' if run.status == 'RUNNING' else '读取已保存的实际运行材料',
                  'model': {'status': model.get('status'), 'calls': model.get('model_calls'),
                            'initially_leaking': diagnosis.get('initially_leaking'),
                            'raw_notes': raw_notes, 'proposals': proposals,
                            'denied_proposal_count': len(row.get('denied_proposals', [])) if row else None},
                  'diagnosis': {'model_suspicion': diagnosis.get('diagnosis'),
                                'confirmed': authority.get('confirmed', 'UNKNOWN'),
                                'repair_authorized': authority.get('repair_authorized')},
                  'tool_calls': len(row.get('tool_trace', [])) if row else None,
                  'unknown_count': unknown_count, 'source_code': original, 'source_sha256': sha(original),
                  'candidate_code': candidate, 'candidate_sha256': sha(candidate) if candidate is not None else None,
                  'diff': ''.join(difflib.unified_diff(original.splitlines(keepends=True), candidate.splitlines(keepends=True),
                                    fromfile='original/tool.py', tofile='candidate/tool.py')) if candidate is not None else None,
                  'evidence': public_evidence, 'validation': validation, 'recheck': recheck,
                  'material_binding': material, 'recheck_applicability': applicable,
                  'historical_recheck': historical_recheck,
                  'stop_reason': task.get('reason') or run.error,
                  'remaining_uncertainty': notes,
                  'process': {'exit_code': run.exit_code, 'raw_streams_retained_locally': run.mode == 'LIVE'},
                  'limitations': ['仅覆盖登记的合成任务与固定检查协议；不表示任意真实项目安全。',
                                  '模型回答与程序判决独立；任务结束不等于验收通过。']}
        from .presentation import story_for
        result['presentation'] = story_for(self, run)
        return safe_public(result)

    def _material(self, run):
        if run.status in ('QUEUED', 'RUNNING') or not (run.method / 'result.json').is_file():
            raise Problem(409, '任务尚无完整材料，不能导出或复检。')
        state = self._material_state(run)
        if state['status'] in ('CHANGED', 'UNAVAILABLE'):
            self._require_current_material(run)
        if run.bundle is None:
            from .bundle import export_bundle
            parent = confined(self.runs_root / ('package-' + uuid.uuid4().hex), self.runs_root)
            try:
                before = self._material_inputs(run)
                export_bundle(run.method, parent)
                after = self._material_inputs(run)
                if before != after:
                    run.material_failure = 'CHANGED'
                    raise Problem(409, '导出期间原始材料变化；未绑定该包，请创建新任务并重新验收。')
                snapshot = {'inputs': after, 'package': self._package_material(parent)}
            except (OSError, ValueError, TypeError, AttributeError):
                run.material_failure = 'UNAVAILABLE'
                raise Problem(409, '完整导出材料或规则绑定不可用；未生成可复用的材料包。')
            run.material_snapshot, run.bundle = snapshot, parent
        self._require_current_material(run)
        return run.bundle

    def recheck(self, identifier):
        if self.access_mode == 'view':
            raise Problem(409, '历史查看入口不执行代码。请使用 start-recheck.cmd。')
        run = self.get(identifier)
        if not self.operation.acquire(blocking=False):
            raise Problem(409, '另一任务或复检正在执行。')
        try:
            from .bundle import recheck_bundle
            material = self._material(run)
            output = confined(self.runs_root / ('recheck-' + uuid.uuid4().hex + '.json'), self.runs_root)
            fresh = recheck_bundle(material, output)
            binding = self._require_current_material(run)
            # The bundle is the authority for this result, never the old UI badge.
            run.recheck = {**fresh, 'validation': validation_view(fresh.get('validation'))}
            run.recheck_binding = binding['binding_sha256']
            return self.view(identifier)
        finally:
            self.operation.release()

    def export(self, identifier):
        run = self.get(identifier)
        if not self.operation.acquire(blocking=False):
            raise Problem(409, '另一任务或复检正在执行。')
        try:
            material = self._material(run)
            archive = confined(self.runs_root / ('export-' + uuid.uuid4().hex + '.zip'), self.runs_root)
            with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as output:
                for path in sorted(material.rglob('*')):
                    confined(path, material)
                    if path.is_file():
                        output.write(path, path.relative_to(material).as_posix())
            self._require_current_material(run)
            return archive
        finally:
            self.operation.release()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, application):
        if address[0] != '127.0.0.1':
            raise ValueError('Only IPv4 loopback is allowed')
        self.application = application
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    server_version = 'CredProofLocal/1'

    def log_message(self, *args):
        pass  # Do not echo untrusted URLs, source text or arbitrary error content.

    def boundary(self):
        port = self.server.server_address[1]
        hosts = self.headers.get_all('Host', [])
        if len(hosts) != 1 or hosts[0] not in (f'127.0.0.1:{port}', f'localhost:{port}'):
            raise Problem(403, '只接受本机服务的 Host。')
        origins = self.headers.get_all('Origin', [])
        if len(origins) > 1 or origins and origins[0] != 'http://' + hosts[0]:
            raise Problem(403, '拒绝跨来源请求。')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise Problem(403, '拒绝跨站请求。')
        if self.headers.get('Transfer-Encoding'):
            raise Problem(400, '不支持分块请求体。')

    def write_headers(self, code, content_type, size, extra=()):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        for name, value in extra:
            self.send_header(name, value)
        self.end_headers()

    def send_json(self, code, value):
        payload = json.dumps(safe_public(value), ensure_ascii=False).encode('utf-8')
        self.write_headers(code, 'application/json; charset=utf-8', len(payload))
        self.wfile.write(payload)

    def body(self):
        if self.headers.get_content_type() != 'application/json':
            raise Problem(415, '请求体必须是 application/json。')
        lengths = self.headers.get_all('Content-Length', [])
        if len(lengths) != 1 or not lengths[0].isdigit():
            raise Problem(400, '缺少明确的请求体长度。')
        size = int(lengths[0])
        if size > 4096:
            raise Problem(413, '请求体超过 4 KiB。')
        self.connection.settimeout(4)
        try:
            data = json.loads(self.rfile.read(size).decode('utf-8'))
        except (ValueError, OSError):
            raise Problem(400, '无效 JSON 请求体。')
        if not isinstance(data, dict):
            raise Problem(400, '请求体必须是对象。')
        return data

    def route(self):
        self.boundary()
        parsed = urlsplit(self.path)
        if parsed.query or parsed.fragment:
            raise Problem(400, '该接口不接受任意查询参数。')
        path = parsed.path
        app = self.server.application
        if self.command == 'GET' and path in ('/', '/index.html', '/styles.css', '/app.js'):
            name = 'index.html' if path == '/' else path[1:]
            target = confined(app.ui / name, app.ui)
            payload = target.read_bytes()
            content_type = {'index.html': 'text/html', 'styles.css': 'text/css', 'app.js': 'text/javascript'}[name]
            self.write_headers(200, content_type + '; charset=utf-8', len(payload))
            self.wfile.write(payload)
            return
        if self.command == 'GET' and path == '/api/agent/health':
            return self.send_json(200, app.runtime())
        if self.command == 'GET' and path == '/api/agent/bootstrap':
            return self.send_json(200, app.bootstrap())
        if self.command == 'POST' and path == '/api/agent/runs':
            data = self.body()
            if set(data) != {'case_id'} or not isinstance(data['case_id'], str):
                raise Problem(400, '仅允许传入已登记的 case_id。')
            return self.send_json(202, app.start(data['case_id']))
        matched = re.fullmatch(r'/api/agent/runs/([a-z0-9_-]+)(/recheck|/export)?', path)
        if matched:
            identifier, operation = matched.groups()
            if self.command == 'GET' and not operation:
                return self.send_json(200, app.view(identifier))
            if self.command == 'POST' and operation == '/recheck':
                if self.body():
                    raise Problem(400, '复检接口不接受路径、代码或判决。')
                return self.send_json(200, app.recheck(identifier))
            if self.command == 'GET' and operation == '/export':
                archive = app.export(identifier)
                self.write_headers(200, 'application/zip', archive.stat().st_size,
                             [('Content-Disposition', f'attachment; filename="credproof-{identifier}.zip"')])
                with archive.open('rb') as source:
                    while block := source.read(65536):
                        self.wfile.write(block)
                return
        raise Problem(404, '没有这个受控资源。')

    def handle_route(self):
        try:
            self.route()
        except Problem as error:
            self.send_json(error.status, {'error': error.message})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.send_json(500, {'error': '本机服务处理失败；未生成安全结论。'})

    do_GET = handle_route
    do_POST = handle_route


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--history', type=Path, action='append', default=[],
                        help='Explicit reviewed C-agent method directory under this checkout runs/')
    args = parser.parse_args()
    application = Application(histories=args.history)
    with Server(('127.0.0.1', args.port), application) as server:
        print(f'CredProof local workbench: http://127.0.0.1:{server.server_address[1]}', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print('Server stopping. Existing execution records remain in runs/ui.', flush=True)


if __name__ == '__main__':
    main()
