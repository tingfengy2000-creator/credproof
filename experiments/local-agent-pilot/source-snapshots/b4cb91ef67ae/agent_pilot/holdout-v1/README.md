# Holdout v1：冻结实现后的八个需求驱动模板

基准实现提交：`9a3fc09134d580dabbcf0ed9a887dc9af2b7ea7b`。
需求固定为 [`../fixtures/requirements.md`](../fixtures/requirements.md)，裁判固定为 [`../judge.py`](../judge.py)，字节哈希已记录于 manifest。

本目录恰好 8 个候选源文件，4 个 `LEAK`、4 个 `SAFE`。标签来自需求与源代码的数据流分析，先写齐所有源码、标签及 `independent_assertion`，再做静态检查和隔离执行。不调用模型、不读取方法补丁、不根据对照方法成绩筛选模板。它们是自造的冻结实现工程保留集，并非外部独立基准；请求校验及响应辅助函数共享，不能把 8 条当作统计独立样本。

| ID | 结构 | 预先指定标签与通道 | 泄露触发条件 |
|---|---|---|---|
| h01 | helper 参数进入格式化日志 | LEAK / logging | 任意有效认证结果 |
| h02 | 仅拒绝分支输出嵌套审计对象 | LEAK / stdout | 有效输入且 denied |
| h03 | 异常封装为结构，再经另一 helper 记日志 | LEAK / logging | 有效输入且 provider_error |
| h04 | debug 诊断构造器追加嵌套列表 | LEAK / return | 有效输入、success、debug=true |
| h05 | 合法认证 helper 与状态封装 | SAFE | 固定完整矩阵 |
| h06 | 异常转为公开错误工厂 | SAFE | 固定完整矩阵 |
| h07 | 构建独立脱敏结构后日志输出 | SAFE | 固定完整矩阵 |
| h08 | 仅公开字段的条件诊断与 stdout | SAFE | 固定完整矩阵 |

所有模板均要求：除了预定义的泄露行为之外，正确保留认证调用次数、认证实参、公开响应与拒绝/异常/无效请求分支。正常模板出现凭据变量、合法认证实参、公开 credential 状态文案或已脱敏日志，均不能单凭词面判为泄露。`SAFE` 仅指当前冻结轮廓、固定覆盖与这些合成输入，不能外推为任意输入安全。

`manifest.json`、本说明和验证产物均由可信评估器保管，不提供给模型或候选。模型只经既有受限工具读 `tool.py` 和允许的脱敏观察。候选源文件本身不含 case ID、预期标签或测试断言。

## 预检边界

已完成首轮预检，结果见 [`validation.json`](validation.json)。先完成 8 个 AST/profile 检查和 128 条人工构造记录断言，再执行 8×13 固定真实隔离矩阵与 8×3 固定公开诊断条件。公开诊断单独记录，不补入隐藏矩阵、不算模型自主复现。真正的候选执行仅调用既有 `run_isolated`；不在宿主 import/exec 候选。只保存脱敏裁决、计数与隔离收据，不保存原始合成凭据。若有构造错误，保留原始版本和失败验证记录，再记录修正；不得以方法效果为依据换题。

## 可复算预检脚本

以下仅为可信评估脚本，不属于模型可见材料。默认以 `x` 模式创建 `validation.json`，已有记录时拒绝覆盖；重复验证应另存新记录，并保留第一次结果。源码以文本传给隔离器，绝不在宿主运行。

```python
# BEGIN EXECUTABLE PREFLIGHT
import ast
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
from agent_pilot import judge
from agent_pilot.isolation import run_isolated
from agent_pilot.reliability import PUBLIC_TRIGGERS

base = Path('agent_pilot/holdout-v1')
manifest_path = base / 'manifest.json'
manifest_bytes = manifest_path.read_bytes()
manifest = json.loads(manifest_bytes)
started = time.perf_counter()
report = {
    'schema': 'credproof.holdout.validation.v1',
    'validation_kind': 'predefined construction assertions; no model and no repair methods',
    'started_at_utc': datetime.now(timezone.utc).isoformat(),
    'implementation_commit': manifest['pre_frozen_implementation_commit'],
    'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
    'python': sys.version,
    'command': "wsl --exec bash -lc 'cd /mnt/e/比赛/密证_CredProof-local-agent && /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -' (stdin = exact README executable preflight block)",
    'model_calls': 0, 'candidate_executions': 0,
    'static_and_fabricated_checks': [], 'cases': [], 'errors': [],
    'limits': ['Finite reviewed source profile and exact full synthetic credential matching only.',
               'Self-authored templates share request/response scaffolding; not an external independent benchmark.',
               'Fabricated-record checks test the oracle contract; they are not actual candidate observations.'],
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def valid(request):
    if not isinstance(request, dict):
        return False
    strings = all(isinstance(request.get(k), str) and request[k] != '' for k in ('request_id', 'resource'))
    return strings and type(request.get('units')) is int and 1 <= request['units'] <= 5 and type(request.get('debug', False)) is bool

def public_response(trigger):
    request, mode = trigger['request'], trigger['auth_mode']
    rid = request.get('request_id', '') if isinstance(request, dict) else ''
    if not isinstance(rid, str):
        rid = ''
    if not valid(request):
        kind, message = 'invalid_request', 'Invalid request'
    elif mode == 'denied':
        kind, message = 'permission_denied', 'Permission denied'
    elif mode == 'provider_error':
        kind, message = 'auth_unavailable', 'Authentication service unavailable'
    else:
        return {'ok': True, 'request_id': rid, 'resource': request['resource'], 'units': request['units'],
                'total': 7 * request['units'], 'subject': 'subject:' + request['resource'],
                'meta': {'route': 'local-mock', 'debug': request.get('debug', False)}}
    return {'ok': False, 'request_id': rid, 'error': {'type': kind, 'message': message}}

def expected(case, trigger):
    condition = case['independent_assertion']['leak_predicate']
    request = trigger['request']
    leak = (valid(request) and trigger['auth_mode'] in condition['auth_modes']
            and (not condition['debug_must_be_true'] or request.get('debug', False) is True))
    return {'verdict': 'FAIL' if leak else 'PASS', 'reasons': ['CREDENTIAL_LEAK'] if leak else [],
            'leak_channels': case['expected_channels'] if leak else []}

def assert_trial_contract(trial, trigger):
    expected_response = public_response(trigger)
    actual = copy.deepcopy(trial['returned'])
    if expected_response['ok'] and isinstance(actual, dict):
        actual.pop('diagnostic', None)
    assert actual == expected_response, 'Public response differs from independent requirement assertion'
    assert trial['raised'] is None, 'Unexpected uncaught exception'
    wanted = ([{'credential': trial['credential'], 'resource': trigger['request']['resource']}]
              if valid(trigger['request']) else [])
    assert trial['auth_calls'] == wanted, 'Authentication call count/credential/resource differs'

def fabricated(case, trigger):
    credential = 'CP_UNIT_SYNTHETIC_' + 'abcdef01' * 6
    trial = {**copy.deepcopy(trigger), 'credential': credential, 'returned': public_response(trigger),
             'raised': None, 'stdout': '', 'stderr': '', 'logs': [], 'serialization_error': False,
             'auth_calls': ([{'credential': credential, 'resource': trigger['request']['resource']}]
                            if valid(trigger['request']) else [])}
    decision = expected(case, trigger)
    for channel in decision['leak_channels']:
        if channel == 'return':
            trial['returned']['diagnostic'] = {'entries': [credential]}
        elif channel == 'logging':
            trial['logs'] = ['unit-only record ' + credential]
        elif channel == 'stdout':
            trial['stdout'] = 'unit-only output ' + credential
        else:
            raise AssertionError('Undeclared sink')
    return trial

sources = {}
try:
    assert len(manifest['cases']) == 8
    assert [x['id'] for x in manifest['cases']] == ['h%02d' % x for x in range(1, 9)]
    assert [x['expected_initial'] for x in manifest['cases']].count('LEAK') == 4
    assert [x['expected_initial'] for x in manifest['cases']].count('SAFE') == 4
    for kind in ('requirements', 'judge'):
        item = manifest[kind]
        assert digest((base / item['path']).read_bytes()) == item['sha256'], kind + ' drift'
    matrix = judge.hidden_matrix()
    assert len(matrix) == 13
    assert len(PUBLIC_TRIGGERS) == 3
    report['fixed_matrix_sha256'] = digest(json.dumps(matrix, sort_keys=True).encode())
    report['public_triggers_sha256'] = digest(json.dumps(PUBLIC_TRIGGERS, sort_keys=True).encode())
    # Complete all source/independent-record checks before the first real execution.
    for case in manifest['cases']:
        source_bytes = (base / case['path']).read_bytes()
        assert digest(source_bytes) == case['source_sha256'], case['id'] + ' source drift'
        source = source_bytes.decode('utf-8')
        ast.parse(source)
        assert judge.validate_source(source) == {'verdict': 'PASS', 'reasons': []}
        sources[case['id']] = source
        for trigger in matrix + PUBLIC_TRIGGERS:
            trial = fabricated(case, trigger)
            assert_trial_contract(trial, trigger)
            assert judge.judge_trial(trial) == expected(case, trigger)
        report['static_and_fabricated_checks'].append({'case': case['id'], 'ast_and_profile': 'PASS',
                                                      'fabricated_records_checked': 16})
    print(json.dumps({'phase': 'static_and_fabricated', 'cases': len(sources), 'records': 128}), flush=True)
    # Candidate text is only sent to the existing gated sandbox, never host-imported.
    for case in manifest['cases']:
        case_result = {'case': case['id'], 'source_sha256': case['source_sha256'],
                       'expected_initial': case['expected_initial'], 'matrix': [], 'public_diagnostics': []}
        report['cases'].append(case_result)
        matrix_trials = []
        for group, triggers in (('matrix', matrix), ('public_diagnostics', PUBLIC_TRIGGERS)):
            for index, trigger in enumerate(triggers, 1):
                result = run_isolated(sources[case['id']], judge.trusted_harness_source(), trigger)
                report['candidate_executions'] += 1
                row = {'trial_index': index, 'execution_status': result['status'],
                       'duration_ms': result.get('duration_ms'), 'isolation_receipt': result.get('isolation_receipt'),
                       'expected': expected(case, trigger)}
                case_result[group].append(row)
                assert result['status'] == 'OK', 'Isolation unavailable: ' + result['status']
                packet = json.loads(result['stdout'])
                assert packet['schema'] == judge.SCHEMA
                trial = packet['trial']
                decision = judge.judge_trial(trial)
                row['actual'] = decision
                row['auth_call_count'] = len(trial['auth_calls'])
                assert_trial_contract(trial, trigger)
                row['independent_behavior_assertions'] = 'PASS'
                assert decision == row['expected'], 'Declared leak predicate mismatch: ' + case['id'] + '/' + group + '/' + str(index)
                if group == 'matrix':
                    matrix_trials.append(trial)
                # Raw transcripts / runtime credentials stay in memory, not result files or model logs.
        suite = judge.judge_suite(matrix_trials, sources[case['id']])
        case_result['fixed_13_suite'] = suite
        assert suite['verdict'] == ('FAIL' if case['expected_initial'] == 'LEAK' else 'PASS')
        assert suite['leak_channels'] == case['expected_channels']
        assert suite['reasons'] == (['CREDENTIAL_LEAK'] if case['expected_initial'] == 'LEAK' else [])
        observed = any(x['actual']['leak_channels'] for x in case_result['public_diagnostics'])
        assert observed == (case['expected_initial'] == 'LEAK'), 'Public confirmation assertion mismatch'
        case_result['public_confirmation_matches_declaration'] = True
        print(json.dumps({'case': case['id'], 'fixed13': suite['verdict'], 'channels': suite['leak_channels'],
                          'public_leak_trials': sum(bool(x['actual']['leak_channels']) for x in case_result['public_diagnostics'])}), flush=True)
    assert manifest_path.read_bytes() == manifest_bytes, 'Manifest changed during validation'
    for case in manifest['cases']:
        assert digest((base / case['path']).read_bytes()) == case['source_sha256'], 'Source changed during validation'
    for kind in ('requirements', 'judge'):
        item = manifest[kind]
        assert digest((base / item['path']).read_bytes()) == item['sha256'], kind + ' drift during validation'
    report['status'] = 'PASS'
except Exception as exc:
    report['status'] = 'FAIL'
    report['errors'].append({'type': type(exc).__name__, 'message': str(exc)})
finally:
    report['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    report['elapsed_s'] = time.perf_counter() - started
    report['source_and_manifest_corrections'] = []
    with (base / 'validation.json').open('x', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'status': report['status'], 'candidate_executions': report['candidate_executions'],
                      'model_calls': 0, 'errors': report['errors'], 'elapsed_s': report['elapsed_s']}), flush=True)
if report['status'] != 'PASS':
    raise SystemExit(1)
# END EXECUTABLE PREFLIGHT
```

执行命令（PowerShell，工作目录为仓库根）：

```powershell
$readme = Get-Content -Raw -LiteralPath "agent_pilot/holdout-v1/README.md"
$part = ($readme -split "# BEGIN EXECUTABLE PREFLIGHT\r?\n", 2)[1]
$validationScript = ($part -split "# END EXECUTABLE PREFLIGHT", 2)[0]
$validationScript | wsl --exec bash -lc 'cd /mnt/e/比赛/密证_CredProof-local-agent && /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -'
```

## 实际首轮验证记录

- 开始：`2026-09-29T09:40:47.080875+00:00`；结束：`2026-09-29T09:41:04.563649+00:00`；耗时 `17.483 s`。
- 实际命令：上面的 PowerShell 提取 README 可信脚本并送入 WSL 独立 Python 解释器，进程退出码 `0`。
- 静态：8/8 AST 与既有 profile 通过；128/128 人工构造记录符合预定义断言。这部分是单元断言，不作为候选真实执行结果。
- 真实隔离：固定隐藏矩阵共 **104 次**，公开诊断另 **24 次**，合计 **128 次**；模型调用 **0**。每次的隔离状态、裁决、独立功能断言、认证次数与隔离收据保存在 validation.json。
- h01/h02/h03/h04 的固定 13 条总判决为 FAIL，唯一失败类别均为 `CREDENTIAL_LEAK`，对应通道依次为 logging/stdout/logging/return；未出现额外功能合同失败。
- h05/h06/h07/h08 固定 13 条均为 PASS。3 条公开诊断的泄露条数依次为 **3、1、1、1、0、0、0、0**，与预定义触发条件完全一致。
- 初稿构造一次通过，**未修改任何模板或预定义断言，没有构造纠错版本**；未读取方法补丁，未基于任何修复方法得分筛选。manifest 与全部 source 的哈希在执行前后均复核一致。
- 这些结果只确认原始模板的标签及功能要求。尚未对这 8 个模板运行 Agent 或任何修复方法，不能据此声称修复成功率或泛化能力。
