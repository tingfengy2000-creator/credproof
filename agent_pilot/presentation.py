"""Curated real records for presentation, never a model or verdict substitute."""
from pathlib import Path
import difflib
import hashlib
import json
import shutil

BATCH = 'experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison'
STORIES = (
    {'case_id': 'h01', 'title': '跨函数的日志泄露', 'subtitle': '模型补丁补足有限规则的结构盲点',
     'phenomenon': '凭据由环境变量读入，经函数参数传递后进入调试日志；源码中没有硬编码密钥。',
     'explanation': '本项目固定启发式未完成这处修改；模型候选消除日志中的凭据，并保留授权认证和必要业务行为。这是该合成案例上的有限增量。'},
    {'case_id': 'h03', 'title': '看似脱敏，仍在泄露', 'subtitle': '真实拒绝 → 反馈 → 调整',
     'phenomenon': '模拟认证服务的异常信息经字典包装进入日志。第一份补丁只插入 [REDACTED] 标记，真实值仍在后面。',
     'explanation': '执行器按合成凭据的实际值匹配：第一份候选有 2 项日志泄露反例；第二份改为固定安全摘要，13 项条件通过。失败原因不是出现 credential 一词。固定流程在本例也直接通过。'},
    {'case_id': 'h07', 'title': '正确脱敏，保持不变', 'subtitle': '合法认证用途与禁止通道分开',
     'phenomenon': '凭据用于授权的本地认证；输出通道已正确脱敏，必要检查没有观察到泄露。',
     'explanation': '保留原代码，完成限定条件下的检查。没有观察到泄露不等于任意输入、任意项目都安全。'},
)


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest_tree(path):
    records = []
    for item in sorted(Path(path).rglob('*')):
        if item.is_symlink() or getattr(item, 'is_junction', lambda: False)():
            raise ValueError('Presentation refuses linked record files')
        if item.is_file():
            records.append((item.relative_to(path).as_posix(), hashlib.sha256(item.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(records).encode()).hexdigest()


def install_demonstrations(app):
    """Make dedicated writable review copies; immutable source records stay untouched."""
    from .web import confined
    app.demonstrations = []
    for story in STORIES:
        source = confined(app.root / BATCH / story['case_id'] / 'C-agent', app.root)
        identity = digest_tree(source)
        destination = confined(app.root / 'runs/demo-replay' / identity[:20] / story['case_id'] / 'C-agent', app.root / 'runs')
        if destination.exists() and digest_tree(destination) != identity:
            # Keep any changed copy, and create a new distinct presentation session.
            from uuid import uuid4
            destination = confined(app.root / 'runs/demo-replay' / (identity[:20] + '-' + uuid4().hex[:8]) / story['case_id'] / 'C-agent', app.root / 'runs')
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
        app.add_history(destination)
        run = next(item for item in app.runs.values() if item.method == destination)
        fixed_path = confined(app.root / BATCH / story['case_id'] / 'A-fixed/result.json', app.root)
        app.demonstrations.append({**story, 'run_id': run.id, 'mode': 'REPLAY',
            'batch': '20260929t095000z-holdout8', 'source_commit': 'b4cb91ef67ae2d14d6cc37f9e18cf6c23e36e8ea',
            'provenance': source.relative_to(app.root).as_posix(), 'record_sha256': identity,
            'fixed_result_sha256': hashlib.sha256(fixed_path.read_bytes()).hexdigest()})


def story_for(app, run):
    story = next((s for s in getattr(app, 'demonstrations', []) if s['run_id'] == run.id), None)
    if not story:
        return None
    if digest_tree(run.method) != story['record_sha256']:
        return None  # A changed replay is no longer the selected historical record.
    original = (run.method / 'original.py').read_text(encoding='utf-8')
    row = read(run.method / 'result.json')
    stages = []
    for candidate in sorted(run.method.glob('candidate-[0-9]*.py')):
        number = candidate.stem.split('-')[-1]
        validation = run.method / f'verify-{number}-validation.json'
        if not validation.is_file():
            continue
        code = candidate.read_text(encoding='utf-8')
        stages.append({'candidate_id': candidate.stem, 'validation': read(validation),
            'sha256': hashlib.sha256(code.encode()).hexdigest(),
            'diff': ''.join(difflib.unified_diff(original.splitlines(True), code.splitlines(True),
                       fromfile='original/tool.py', tofile=candidate.name))})
    from .web import confined
    fixed_path = confined(app.root / BATCH / run.case_id / 'A-fixed/result.json', app.root)
    if hashlib.sha256(fixed_path.read_bytes()).hexdigest() != story['fixed_result_sha256']:
        return None
    fixed = read(fixed_path)
    return {**story, 'stages': stages,
        'fixed_comparison': {'method': 'A-fixed', 'verdict': fixed['final_validation']['verdict'],
            'task_status': fixed['task']['task_status']},
        'initial_confirmation': row.get('initial_authority', {}).get('confirmed'),
        'notice': '精选的真实历史记录，不是本次模型推理；不代表总体成功率。'}
