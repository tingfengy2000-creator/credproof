"""Synthetic-only acceptance pilot. No case labels, network authentication or repository execution.

A contract fixes a before snapshot and an exact permitted edit. Check receipts bind
to the complete candidate identity, actual scope, rules and validator. Rechecking
reads material and runs checks again; a saved verdict is never an input verdict.
"""
import ast
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import time
from types import SimpleNamespace

from .scanner import safe_relative, sha

CHECKS = ('scan', 'syntax', 'function', 'removal', 'allowed_changes')
MAX_FILE = 128 * 1024
MAX_FILES = 32
TOKEN = re.compile(r'CP_SYNTH_[A-F0-9]{24}\Z')
PROFILE = 'authorization-header-v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def digest(value):
    return sha(canonical(value))


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def _redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, '<redacted-target>')
    if isinstance(value, dict):
        return {_redact(k, secret): _redact(v, secret) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(x, secret) for x in value]
    return value


def public_contract(bundle):
    contract, private, _, _ = _load(bundle)
    return {'view': 'sanitized-contract-view; recheck requires original local material',
            'contract': _redact(contract, private['target_value'])}


def validator_id():
    # Binds the verifier implementation, not a claim of trusted execution or certification.
    return digest({p.name: sha(p.read_bytes()) for p in (Path(__file__), Path(__file__).with_name('scanner.py'))})


def _scope(names):
    checked = sorted(safe_relative(x) for x in names)
    if not checked or len(checked) > MAX_FILES or len({x.casefold() for x in checked}) != len(checked):
        raise ValueError('Scope must contain 1..32 unique explicit paths')
    return checked


def _read(root, relative):
    root = Path(root).resolve(strict=True)
    path = root
    for part in safe_relative(relative).split('/'):
        path = path / part
        metadata = path.lstat()
        if stat.S_ISLNK(metadata.st_mode) or getattr(path, 'is_junction', lambda: False)():
            raise ValueError('Links and junctions are not supported')
    if not path.is_file() or not path.resolve().is_relative_to(root):
        raise ValueError('Not an in-root regular file')
    before = path.stat()
    if before.st_size > MAX_FILE:
        raise ValueError('File exceeds pilot limit')
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns) or len(data) > MAX_FILE:
        raise ValueError('File changed during capture')
    data.decode('utf-8-sig')
    return data


def _tree(root):
    files, errors = {}, {}
    root = Path(root)
    if not root.is_dir() or root.is_symlink() or getattr(root, 'is_junction', lambda: False)():
        return files, {'<root>': 'missing_or_linked_directory'}
    seen = 0
    for directory, dirs, names in os.walk(root, followlinks=False):
        for name in list(dirs):
            item = Path(directory) / name
            if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
                errors[item.relative_to(root).as_posix()] = 'directory_link'
                dirs.remove(name)
            elif name == '.git':
                errors[item.relative_to(root).as_posix()] = 'unexpected_git_directory'
                dirs.remove(name)
        for name in sorted(names):
            seen += 1
            relative = (Path(directory) / name).relative_to(root).as_posix()
            if seen > MAX_FILES:
                errors['<limit>'] = 'too_many_files'
                return files, errors
            try:
                files[relative] = _read(root, relative)
            except (OSError, ValueError, UnicodeError):
                errors[relative] = 'unreadable_or_unsupported'
    return files, errors


def _manifest(files):
    return {name: sha(value) for name, value in sorted(files.items())}


def _git(repo, args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
    env['GIT_OPTIONAL_LOCKS'] = '0'
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=',
                             '-C', str(repo), *args], capture_output=True, timeout=10, env=env)
    if result.returncode:
        raise ValueError('Git read failed')
    return result.stdout


def _capture(repo, source, scope):
    if source == 'worktree':
        return {name: _read(repo, name) for name in scope}
    if source != 'index':
        raise ValueError('Only worktree and index are supported')
    records = _git(repo, ['ls-files', '--stage', '-z', '--', *scope])
    entries = {}
    for record in records.split(b'\0'):
        if not record:
            continue
        metadata, name = record.split(b'\t', 1)
        mode, oid, stage = metadata.decode().split()
        relative = name.decode('utf-8')
        if relative not in scope or mode not in ('100644', '100755') or stage != '0':
            raise ValueError('Unmerged, linked or unexpected index object')
        if not re.fullmatch('[a-f0-9]{40,64}', oid):
            raise ValueError('Invalid index object ID')
        size = int(_git(repo, ['cat-file', '-s', oid]))
        if size > MAX_FILE:
            raise ValueError('Index object exceeds pilot limit')
        data = _git(repo, ['cat-file', 'blob', oid])
        data.decode('utf-8-sig')
        entries[relative] = data
    if set(entries) != set(scope):
        raise ValueError('Not all declared paths have ordinary index entries')
    return entries


def _planned(before, target, symbol, env_name):
    data = before[target]
    if data.startswith(b'\xef\xbb\xbf'):
        raise ValueError('Pilot patch offsets require UTF-8 without BOM')
    tree = ast.parse(data.decode('utf-8'))
    assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                   and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and n.targets[0].id == symbol]
    if len(assignments) != 1:
        raise ValueError('Requires one simple module-level target assignment')
    node = assignments[0]
    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str) or node.lineno != node.end_lineno:
        raise ValueError('Requires a single-line string literal')
    secret = node.value.value
    if not TOKEN.fullmatch(secret):
        raise ValueError('This pilot accepts only non-authenticating CP_SYNTH fixture markers')
    if not re.fullmatch('[A-Z][A-Z0-9_]{0,63}', env_name):
        raise ValueError('Invalid environment variable name')
    if symbol != 'SERVICE_TOKEN':
        raise ValueError('Pilot functional profile supports SERVICE_TOKEN only')
    imports = [n for n in tree.body if isinstance(n, ast.Import) and len(n.names) == 1
               and n.names[0].name == 'os' and n.names[0].asname is None]
    # No broad import rewriting: supported source must already import os explicitly.
    if len(imports) != 1:
        raise ValueError('Pilot source must already contain one plain import os')
    lines = data.splitlines(keepends=True)
    start = sum(map(len, lines[:node.value.lineno - 1])) + node.value.col_offset
    end = sum(map(len, lines[:node.value.end_lineno - 1])) + node.value.end_col_offset
    replacement = ('os.environ[' + json.dumps(env_name) + ']').encode()
    expected = dict(before)
    expected[target] = data[:start] + replacement + data[end:]
    edit = {'file': target, 'start': start, 'end': end, 'replacement_sha256': sha(replacement)}
    return secret, expected, edit


def freeze(repo, bundle, scanner, *, source='index', scope=('config.py', 'notes.txt'),
           target='config.py', symbol='SERVICE_TOKEN', env_name='CP_DEMO_TOKEN', allow_fixture=False):
    repo = Path(repo).resolve(strict=True)
    bundle = Path(bundle).resolve()
    if bundle == repo or bundle.is_relative_to(repo) or repo.is_relative_to(bundle):
        raise ValueError('Bundle must be separate from the source repository')
    if bundle.exists():
        raise ValueError('Refuse to overwrite an existing bundle')
    scope = _scope(scope)
    target = safe_relative(target)
    if target not in scope:
        raise ValueError('Target outside frozen scope')
    _git(repo, ['rev-parse', '--show-toplevel'])
    before = _capture(repo, source, scope)
    original = {}
    for layer in ('worktree', 'index'):
        try:
            original[layer] = _manifest(_capture(repo, layer, scope))
        except (ValueError, OSError, UnicodeError):
            original[layer] = None
    if _manifest(before) != _manifest(_capture(repo, source, scope)):
        raise ValueError('Source changed during freeze')
    secret, expected, edit = _planned(before, target, symbol, env_name)
    key = os.urandom(32)
    contract = {'schema': 'credproof-contract/1', 'source': source, 'scope': scope,
                'target': target, 'symbol': symbol, 'env_name': env_name,
                'before_manifest': _manifest(before), 'expected_manifest': _manifest(expected),
                'allowed_edit': edit, 'original_manifests': original,
                'target_fingerprint': hmac.new(key, secret.encode(), hashlib.sha256).hexdigest(),
                'scanner': scanner.descriptor(), 'validator_id': validator_id(),
                'function_profile': PROFILE if allow_fixture else None,
                'required_checks': list(CHECKS), 'limits': {'files': MAX_FILES, 'bytes_per_file': MAX_FILE},
                'claim': 'specified candidate only; no application or revocation claim'}
    contract['contract_id'] = digest(contract)
    bundle.mkdir(parents=True)
    for folder, objects in [('before', before), ('candidate', expected)]:
        for name, value in objects.items():
            path = bundle / folder / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(value)
    write_json(bundle / 'contract.json', contract)
    # Private witness and source path are not included in shareable reports.
    write_json(bundle / 'private.json', {'contract_id': contract['contract_id'], 'repo': str(repo),
                                       'target_value': secret, 'hmac_key': key.hex()})
    return contract


def _load(bundle):
    bundle = Path(bundle).resolve(strict=True)
    contract = json.loads((bundle / 'contract.json').read_text(encoding='utf-8'))
    private = json.loads((bundle / 'private.json').read_text(encoding='utf-8'))
    unsigned = {k: v for k, v in contract.items() if k != 'contract_id'}
    if digest(unsigned) != contract['contract_id'] or private['contract_id'] != contract['contract_id']:
        raise ValueError('Contract does not match local anchor')
    if contract['required_checks'] != list(CHECKS):
        raise ValueError('Unsupported acceptance conditions')
    _scope(contract['scope'])
    before, errors = _tree(bundle / 'before')
    if errors or _manifest(before) != contract['before_manifest']:
        raise ValueError('Frozen before material is missing or changed')
    secret, expected, edit = _planned(before, contract['target'], contract['symbol'], contract['env_name'])
    if secret != private['target_value'] or _manifest(expected) != contract['expected_manifest'] or edit != contract['allowed_edit']:
        raise ValueError('Plan cannot be independently reconstructed')
    fingerprint = hmac.new(bytes.fromhex(private['hmac_key']), secret.encode(), hashlib.sha256).hexdigest()
    if fingerprint != contract['target_fingerprint']:
        raise ValueError('Private witness does not match target identity')
    return contract, private, before, expected


def _binding(contract, files, errors, scope, scanner):
    return {'contract_id': contract['contract_id'],
            'candidate_id': digest({'manifest': _manifest(files), 'errors': errors}),
            'scope_id': digest(scope), 'rules_id': digest(scanner.descriptor()),
            'validator_id': validator_id()}


def _status(status, reason, **details):
    return {'status': status, 'reason': reason, **details}


def _syntax(files):
    bad = []
    for name, value in files.items():
        if name.endswith('.py'):
            try:
                ast.parse(value.decode('utf-8-sig'))
            except (SyntaxError, ValueError, UnicodeError):
                bad.append(name)
    return _status('FAIL' if bad else 'PASS', 'syntax_error' if bad else 'syntax_valid', files=bad)


def _safe_expr(node):
    if isinstance(node, ast.Constant):
        return type(node.value) in (str, int, bool, type(None)) and len(str(node.value)) < MAX_FILE
    if isinstance(node, ast.Name):
        return node.id == 'SERVICE_TOKEN'
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _safe_expr(node.left) and _safe_expr(node.right)
    def environ(n):
        return isinstance(n, ast.Attribute) and n.attr == 'environ' and isinstance(n.value, ast.Name) and n.value.id == 'os'
    if isinstance(node, ast.Subscript):
        return environ(node.value) and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str)
    if isinstance(node, ast.Call):
        return (isinstance(node.func, ast.Attribute) and node.func.attr == 'get' and environ(node.func.value)
                and not node.keywords and 1 <= len(node.args) <= 2
                and all(isinstance(a, ast.Constant) and isinstance(a.value, str) for a in node.args))
    return False


def _function(files, contract):
    if contract['function_profile'] != PROFILE:
        return _status('UNKNOWN', 'no_authorized_function_profile')
    data = files.get(contract['target'])
    if data is None:
        return _status('UNKNOWN', 'function_target_not_observed')
    try:
        tree = ast.parse(data.decode('utf-8-sig'))
    except (SyntaxError, ValueError, UnicodeError):
        return _status('UNKNOWN', 'function_not_run_syntax_invalid')
    if len(list(ast.walk(tree))) > 150:
        return _status('UNKNOWN', 'outside_fixture_language')
    body, funcs, assignments = [], 0, 0
    for node in tree.body:
        if isinstance(node, ast.Import) and len(node.names) == 1 and node.names[0].name == 'os' and node.names[0].asname is None:
            continue  # Supply a tiny in-memory environ object; never import an arbitrary module.
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name == 'SERVICE_TOKEN' and _safe_expr(node.value):
                assignments += 1
                body.append(node)
                continue
            if name not in ('os', 'authorization_header') and not name.startswith('_') and isinstance(node.value, ast.Constant) and _safe_expr(node.value):
                body.append(node)
                continue
        if (isinstance(node, ast.FunctionDef) and node.name == 'authorization_header'
                and not node.decorator_list and not node.returns and not getattr(node, 'type_params', [])
                and not node.args.args and not node.args.posonlyargs and not node.args.kwonlyargs
                and node.args.vararg is None and node.args.kwarg is None
                and len(node.body) == 1 and isinstance(node.body[0], ast.Return)
                and _safe_expr(node.body[0].value)):
            funcs += 1
            body.append(node)
            continue
        return _status('UNKNOWN', 'outside_fixture_language')
    if funcs != 1 or assignments != 1:
        return _status('UNKNOWN', 'fixture_shape_not_supported')
    code = compile(ast.Module(body=body, type_ignores=[]), '<approved-fixture>', 'exec')
    for value in ('runtime-test-alpha', 'runtime-test-beta'):
        namespace = {'__builtins__': {}, 'os': SimpleNamespace(environ={contract['env_name']: value})}
        try:
            exec(code, namespace)  # Only the closed grammar above, with no real os or builtins.
            if namespace['authorization_header']() != 'Bearer ' + value:
                return _status('FAIL', 'wrong_behavior_when_variable_present')
        except Exception:
            return _status('FAIL', 'exception_when_variable_present')
    try:
        namespace = {'__builtins__': {}, 'os': SimpleNamespace(environ={})}
        exec(code, namespace)
        namespace['authorization_header']()
    except KeyError:
        return _status('PASS', 'two_present_values_and_missing_value_checked', assertions=3)
    except Exception:
        return _status('FAIL', 'unexpected_missing_variable_error')
    return _status('FAIL', 'missing_variable_did_not_fail')


def _removal(files, secret):
    found = []
    for name, data in files.items():
        present = secret.encode() in data
        if not present and name.endswith('.py'):
            try:
                present = any(isinstance(n, ast.Constant) and n.value == secret for n in ast.walk(ast.parse(data.decode('utf-8-sig'))))
            except (SyntaxError, UnicodeError, ValueError):
                pass
        if present:
            found.append(name)
    return _status('FAIL' if found else 'PASS', 'target_residual' if found else 'target_removed', files=found,
                   representations=['exact_utf8_bytes', 'parseable_python_string_literals'])


def collect(bundle, scanner, *, scope_override=None, skip=()):
    started = time.perf_counter()
    contract, private, before, expected = _load(bundle)
    scope = _scope(scope_override if scope_override is not None else contract['scope'])
    files, errors = _tree(Path(bundle) / 'candidate')
    observed = {name: files[name] for name in scope if name in files}
    incomplete = bool(errors) or set(observed) != set(scope)
    binding = _binding(contract, files, errors, scope, scanner)
    checks = {}
    def run(name, callback):
        if name in skip:
            return
        t = time.perf_counter()
        result = callback()
        if incomplete and result['status'] == 'PASS':
            result = _status('UNKNOWN', 'candidate_read_incomplete')
        result.update(binding=copy.deepcopy(binding), duration_ms=(time.perf_counter() - t) * 1000)
        checks[name] = result
    run('scan', lambda: scanner.scan(observed))
    run('syntax', lambda: _syntax(observed))
    run('function', lambda: _function(observed, contract))
    run('removal', lambda: _removal(observed, private['target_value']))
    def changes():
        extras = sorted(set(files) - set(expected))
        changed = sorted(name for name in observed if name in expected and observed[name] != expected[name])
        if extras or changed:
            return _status('FAIL', 'outside_frozen_edit', files=extras + changed)
        if errors or set(files) != set(expected):
            return _status('UNKNOWN', 'missing_or_unreadable_candidate_material')
        return _status('PASS', 'exact_planned_change')
    run('allowed_changes', changes)
    final_files, final_errors = _tree(Path(bundle) / 'candidate')
    stable = digest({'files': _manifest(files), 'errors': errors}) == digest({'files': _manifest(final_files), 'errors': final_errors})
    if not stable or binding['rules_id'] != digest(scanner.descriptor()):
        for check in checks.values():
            check.update(status='UNKNOWN', reason='candidate_or_rules_changed_during_checks')
    evidence = {'schema': 'credproof-evidence/1', 'binding': binding, 'scope': scope,
            'candidate_manifest': _manifest(files), 'read_errors': errors,
            'stable_during_collection': stable, 'checks': checks,
            'duration_ms': (time.perf_counter() - started) * 1000}
    return _redact(evidence, private['target_value'])


def _remaining(private, contract, accepted_manifest):
    result = {'external_revocation': 'UNKNOWN', 'history': 'NOT_SCANNED'}
    for layer in ('worktree', 'index'):
        try:
            files = _capture(Path(private['repo']), layer, contract['scope'])
            present = _removal(files, private['target_value'])['status'] == 'FAIL'
            result[layer] = {'presence': 'PRESENT' if present else 'ABSENT_WITHIN_SCOPE',
                             'scope': contract['scope'], 'coverage': 'COMPLETE',
                             'unchanged_since_freeze': _manifest(files) == contract['original_manifests'][layer],
                             'matches_candidate': _manifest(files) == accepted_manifest,
                             'observation': 'current_origin_read_separately_from_frozen_before_material'}
        except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired):
            result[layer] = {'presence': 'FAILED', 'coverage': 'INCOMPLETE', 'matches_candidate': None}
    return result


def assess(bundle, evidence, scanner, *, mode='C'):
    started = time.perf_counter()
    if mode not in ('A', 'B', 'C', 'C-no-binding'):
        raise ValueError('Unknown comparison policy')
    try:
        contract, private, before, expected = _load(bundle)
    except (OSError, ValueError, KeyError, UnicodeError):
        return {'verdict': 'UNKNOWN', 'mode': mode, 'applicability': 'UNAVAILABLE',
                'obligations': {}, 'reasons': ['contract_or_before_material_invalid'],
                'duration_ms': (time.perf_counter() - started) * 1000}
    files, errors = _tree(Path(bundle) / 'candidate')
    current = _binding(contract, files, errors, contract['scope'], scanner)
    needed = {'A': ('scan',), 'B': ('scan', 'syntax', 'function'), 'C': CHECKS, 'C-no-binding': CHECKS}[mode]
    obligations, reasons = {}, []
    applicable = 'CURRENT'
    frozen_rules = digest(contract['scanner'])
    for name in needed:
        check = evidence.get('checks', {}).get(name)
        if not isinstance(check, dict) or check.get('status') not in ('PASS', 'FAIL', 'UNKNOWN'):
            obligations[name] = _status('UNKNOWN', 'missing_or_invalid_evidence')
            reasons.append(name + ':missing_or_invalid_evidence')
            continue
        if mode == 'C':
            if check.get('binding') != current or current['rules_id'] != frozen_rules or current['validator_id'] != contract['validator_id']:
                obligations[name] = _status('UNKNOWN', 'evidence_not_applicable_to_current_contract')
                reasons.append(name + ':binding_mismatch')
                applicable = 'STALE_OR_MISMATCHED'
                continue
        obligations[name] = {k: v for k, v in check.items() if k not in ('binding', 'duration_ms')}
    states = [x['status'] for x in obligations.values()]
    verdict = 'FAIL' if 'FAIL' in states else 'UNKNOWN' if 'UNKNOWN' in states else 'PASS'
    report = {'schema': 'credproof-report/1', 'mode': mode, 'verdict': verdict, 'applicability': applicable,
              'contract_id': contract['contract_id'], 'current_binding': current,
              'scope': contract['scope'], 'required_checks': list(needed), 'obligations': obligations,
              'reasons': reasons, 'candidate_read_errors': errors,
              'candidate_manifest': _manifest(files),
              'remaining_risks': _remaining(private, contract, _manifest(files)),
              'application_boundary': 'A local-copy PASS may remain valid if the original repository changes; applying its patch requires a separate current-source match.',
              'claim': 'Only the specified candidate and declared conditions; not incident closure or credential revocation',
              'limitations': ['synthetic-only', 'one restricted Python assignment', 'closed functional fixture grammar',
                              'local untrusted hashes are not signatures or third-party attestation']}
    report['duration_ms'] = (time.perf_counter() - started) * 1000
    return _redact(report, private['target_value'])


def recheck(bundle, scanner):
    """Re-read frozen/current material and rerun every obligation, ignoring saved verdicts."""
    try:
        evidence = collect(bundle, scanner)
    except (OSError, ValueError, KeyError, UnicodeError):
        return {'verdict': 'UNKNOWN', 'mode': 'C', 'applicability': 'UNAVAILABLE', 'obligations': {},
                'reasons': ['required_material_not_available_for_recheck']}
    return assess(bundle, evidence, scanner)
