"""Portable synthetic review material. Hashes describe bytes, not authenticity.

An imported package never supplies executable code to the running API: rechecks
use this installed verifier and the caller's pinned scanner executable. The
standalone entry is for reviewers who have chosen to trust this release's code.
"""
import json
from pathlib import Path
import shutil

from . import core
from .scanner import Gitleaks, safe_relative, sha

SCHEMA = 'credproof-portable-synthetic/2'
APPROVED_RULES_SHA256 = '7cd61945ba9759186cbaff7285bfc56f86addcb25cdb78e97ba444178983db02'
TRUST = [
    'Synthetic source, declared requirements and authorization profile are trusted inputs.',
    'The reviewer must trust the installed verifier and pinned Gitleaks executable.',
    'Hashes and the included synthetic witness are unsigned and forgeable together; not third-party attestation.',
    'Origin snapshots describe export-time observations, not the live original repository.',
    'The closed functional grammar never executes arbitrary project scripts.',
]


def _write_files(root, files):
    for name, data in files.items():
        path = root / safe_relative(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))


def _json(path):
    if path.is_symlink() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Linked or oversized package metadata')
    return json.loads(path.read_text(encoding='utf-8'))


def export_package(bundle, scanner, destination, *, history=(), synthetic_confirmed=False):
    """Export ONLY explicitly confirmed synthetic material; refuse overwrite.

    history entries contain evidence/report/label and actual candidate_files
    captured at the corresponding check. No historical object is reconstructed
    from a report or the canonical plan.
    """
    if not synthetic_confirmed:
        raise ValueError('Explicit synthetic-only confirmation required')
    bundle, destination = Path(bundle).resolve(strict=True), Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(bundle):
        raise ValueError('Destination must be new and separate')
    contract, private, before, _ = core._load(bundle)
    candidate, errors = core._tree(bundle / 'candidate')
    if errors:
        raise ValueError('Cannot export unreadable candidate')
    destination.mkdir(parents=True)
    target = destination / 'bundle'
    _write_files(target / 'before', before)
    _write_files(target / 'candidate', candidate)
    core.write_json(target / 'contract.json', contract)
    witness = {key: private[key] for key in ('contract_id', 'target_value', 'hmac_key')}
    witness.update(origin_kind='exported-synthetic-snapshots', synthetic=True)
    core.write_json(target / 'private.json', witness)
    origin = {}
    for layer in ('worktree', 'index'):
        try:
            if private.get('origin_kind') == 'exported-synthetic-snapshots':
                files = {name: core._read(bundle / 'origin' / layer, name) for name in contract['scope']}
            else:
                files = core._capture(Path(private['repo']), layer, contract['scope'])
            _write_files(target / 'origin' / layer, files)
            origin[layer] = {'status': 'CAPTURED', 'manifest': core._manifest(files)}
        except (OSError, ValueError, KeyError, UnicodeError):
            origin[layer] = {'status': 'UNAVAILABLE'}
    (destination / 'rules.toml').write_bytes(scanner.config.read_bytes())
    snapshots = []
    for i, item in enumerate(history):
        folder = destination / 'history' / f'{i:03d}'
        folder.mkdir(parents=True)
        core.write_json(folder / 'evidence.json', item['evidence'])
        core.write_json(folder / 'report.json', item['report'])
        captured = item.get('candidate_files')
        if captured is None:
            raise ValueError('History requires the actual captured candidate files')
        _write_files(folder / 'candidate', captured)
        actual, problems = core._tree(folder / 'candidate')
        if problems or core._manifest(actual) != item['evidence'].get('candidate_manifest'):
            raise ValueError('Historical candidate does not match its receipt')
        snapshots.append({'directory': f'history/{i:03d}', 'label': str(item.get('label', 'check'))})
    if not snapshots:
        evidence = core.collect(bundle, scanner)
        report = core.assess(bundle, evidence, scanner)
        folder = destination / 'history/000'
        folder.mkdir(parents=True)
        core.write_json(folder / 'evidence.json', evidence)
        core.write_json(folder / 'report.json', report)
        _write_files(folder / 'candidate', candidate)
        snapshots.append({'directory': 'history/000', 'label': 'export-time-check'})
    runtime = destination / 'runtime/credproof'
    runtime.mkdir(parents=True)
    for name in ('__init__.py', 'core.py', 'scanner.py', 'portable.py'):
        shutil.copyfile(Path(__file__).with_name(name), runtime / name)
    installer = Path(__file__).resolve().parents[1] / 'scripts/get_gitleaks.py'
    (destination / 'scripts').mkdir()
    shutil.copyfile(installer, destination / 'scripts/get_gitleaks.py')
    (destination / 'recheck.py').write_text(STANDALONE, encoding='utf-8', newline='\n')
    (destination / 'README.md').write_text(README, encoding='utf-8', newline='\n')
    core.write_json(destination / 'portable.json', {
        'schema': SCHEMA, 'synthetic': True, 'generated_at_utc': core.utc_now(),
        'bundle': 'bundle', 'rules': 'rules.toml', 'history': snapshots,
        'origin_observations': origin, 'trust': TRUST,
        'validator_id': core.validator_id(), 'scanner': scanner.descriptor(),
    })
    manifest = {p.relative_to(destination).as_posix(): {'sha256': sha(p.read_bytes()), 'size': p.stat().st_size}
                for p in sorted(destination.rglob('*')) if p.is_file()}
    core.write_json(destination / 'material-manifest.json', {'files': manifest,
                    'meaning': 'Export byte inventory, excluding itself. Not a signature.'})
    return destination


def recheck_package(package, executable):
    """Reread material, evaluate old receipt bindings, then execute fresh checks."""
    package = Path(package).resolve(strict=True)
    # Fixed layouts only; no user-specified source paths or commands are followed.
    for path in package.rglob('*'):
        if path.is_symlink() or getattr(path, 'is_junction', lambda: False)():
            raise ValueError('Package links are not allowed')
        safe_relative(path.relative_to(package).as_posix())
    metadata = _json(package / 'portable.json')
    if (metadata.get('schema') != SCHEMA or metadata.get('synthetic') is not True
            or metadata.get('bundle') != 'bundle' or metadata.get('rules') != 'rules.toml'):
        raise ValueError('Unsupported portable layout')
    bundle = package / 'bundle'
    private = _json(bundle / 'private.json')
    if 'repo' in private or private.get('origin_kind') != 'exported-synthetic-snapshots':
        raise ValueError('Imported material cannot refer to a live repository')
    if sha((package / 'rules.toml').read_bytes()) != APPROVED_RULES_SHA256:
        raise ValueError('Portable import accepts only this release\'s reviewed synthetic rules')
    scanner = Gitleaks(executable, package / 'rules.toml')
    manifest = _json(package / 'material-manifest.json')
    differences = []
    for name, entry in manifest['files'].items():
        path = package / safe_relative(name)
        if not path.is_file() or sha(path.read_bytes()) != entry['sha256']:
            differences.append(name)
    histories = []
    for entry in metadata['history']:
        directory = safe_relative(entry['directory'])
        if not directory.startswith('history/') or len(directory.split('/')) != 2:
            raise ValueError('Invalid history location')
        evidence = _json(package / directory / 'evidence.json')
        saved = _json(package / directory / 'report.json')
        old_files, errors = core._tree(package / directory / 'candidate')
        histories.append({'label': entry['label'], 'saved_verdict_untrusted': saved.get('verdict'),
                          'old_object_material_matches_receipt': not errors and core._manifest(old_files) == evidence.get('candidate_manifest'),
                          'applicability': core.evidence_applicability(bundle, evidence, scanner)})
    try:
        fresh_evidence = core.collect(bundle, scanner)
        fresh_report = core.assess(bundle, fresh_evidence, scanner)
    except (OSError, ValueError, KeyError, UnicodeError):
        fresh_evidence = None
        fresh_report = core.recheck(bundle, scanner)
    return {'schema': 'credproof-portable-recheck/2', 'checked_at_utc': core.utc_now(),
            'material_inventory_differences': differences,
            'old_evidence_applicability': histories[-1]['applicability'] if histories else {'status': 'INSUFFICIENT'},
            'history': histories, 'fresh_report': fresh_report, 'fresh_evidence': fresh_evidence,
            'trust': TRUST, 'limitations': ['Windows pinned binary identity; no cross-platform validation claim',
                                          'Saved verdict fields were not used to decide the fresh verdict']}


STANDALONE = '''"""Review this release's code before executing it. Synthetic material only."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
from credproof.portable import recheck_package
p = argparse.ArgumentParser()
p.add_argument("--gitleaks", type=Path, default=ROOT / ".tools/gitleaks-8.28.0" / ("gitleaks.exe" if sys.platform == "win32" else "gitleaks"))
p.add_argument("--output", type=Path)
a = p.parse_args()
result = recheck_package(ROOT, a.gitleaks)
text = json.dumps(result, ensure_ascii=False, indent=2) + "\\n"
if a.output:
    if a.output.exists():
        raise SystemExit("Refuse to overwrite previous result")
    a.output.write_text(text, encoding="utf-8")
print(text)
'''

README = '''# 可搬移的合成复检材料

所有 CP_SYNTH 值仅为合成标记，不能认证任何服务。这里不是脱敏后的真实泄露事件。

将本目录完整复制到新的目录（含 runtime、before、candidate、history），使用 Python 3.12 或更高版本：

```powershell
python scripts/get_gitleaks.py
python recheck.py --output fresh-recheck.json
```

也可用 `--gitleaks <已校验的8.28.0可执行文件>`。本版本实际在 Windows 验证；不同平台的扫描器二进制身份不同，旧契约可能 UNKNOWN，未声称跨平台验收。

复检重新读取材料与适用性、执行五项必要检查；保存的 verdict 只供比较，不参与新判决。
history 保留实际检查时的副本；bundle/candidate 是当前对象。旧报告不适用与当前 FAIL 是两个独立问题。
material-manifest.json 只记录导出时文件字节。后续副本改变会单独列出差异，仍按当前材料重新检查。

信任边界：信任人工声明的需求、契约、封闭功能配置，以及经审查的本地验证器与 Gitleaks。
普通哈希、合成 witness 和 JSON 均可一起改写，不是签名、第三方认证或不可伪造证明。
origin/worktree 和 origin/index 是导出时读取的快照，复检不会联系原电脑，也不声称它们仍为当前状态。
外部撤销一直未知。不要用该入口运行未经审查的任意项目脚本。
'''
