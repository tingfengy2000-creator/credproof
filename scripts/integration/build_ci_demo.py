"""Derive docs/integration/ci-demo.json (credproof.ci-demo/v1) from the C acceptance evidence.

Offline and deterministic: reads only committed files under
docs/integration/evidence/ci-c and the committed workflow/target list. No
network, no GitHub API, no model. Copies verdicts, exit codes, condition
facts and acceptance counters; no URLs, run identifiers, account names or
host paths enter the output (checked before writing).

    python scripts/integration/build_ci_demo.py [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / 'docs/integration/evidence/ci-c'
OUTPUT = ROOT / 'docs/integration/ci-demo.json'
sys.path.insert(0, str(ROOT))
from credproof_safety.report_formats import CONDITIONS  # noqa: E402

LABELS = {'credproof/' + key: label for key, label, _, _ in CONDITIONS}
CONTROLS = {
    'vulnerable': {'title': '提交漏洞补丁的 PR',
                   'origin': '入口文件与 Qwen3-Coder 30B 在评测中交回的“修复”逐字节相同，即未修改的漏洞原版。'},
    'reference': {'title': '提交参考修复的 PR', 'origin': '人工编写的参考修复，不是新的 AI 输出。'},
}
FORBIDDEN = re.compile(r'https?://|github\.com|/home/|/Users/|[A-Za-z]:\\\\|runner/work', re.I)


def read(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def job(control: str, environment: str, row: dict) -> dict:
    base = EVIDENCE / 'runs' / control / environment
    report = read(base / 'target-0' / 'report.json')
    observation = (report.get('execution') or {}).get('pytest_observation') or {}
    required = [c for c in (observation.get('cases') or {}).values() if c.get('required') is True]
    return {
        'environment': environment,
        'verdict': row['verdict'],
        'exit_code': row['check_exit_code'],
        'business_tests': {'required': len(required), 'passed': sum(c.get('passed', 0) for c in required),
                           'all_passed': observation.get('required_tests_passed') is True},
        'failed_checks': row['failed_checks'],
        'doctor_ready': row['doctor_ready'],
        'anchors_matched': row['anchors_matched'],
        'check_duration_ms': report.get('duration_ms'),
    }


def build() -> dict:
    results = read(EVIDENCE / 'results.json')
    rows = {(r['control'], r['environment']): r for r in results['rows']}
    controls = []
    for control, meta in CONTROLS.items():
        sarif = read(EVIDENCE / 'runs' / control / 'container' / 'sarif' / 'target-0.sarif')['runs'][0]
        findings = [{'rule': r['ruleId'], 'condition': LABELS.get(r['ruleId'], r['ruleId']), 'fact': r['message']['text'],
                     'level': r['level']} for r in sarif['results']]
        controls.append({'id': control, **meta,
                         'jobs': [job(control, env, rows[(control, env)]) for env in ('native', 'container')],
                         'sarif_results': findings,
                         'sarif_category': sarif['automationDetails']['id'],
                         'tool_version': sarif['tool']['driver']['version']})
    container = rows[('reference', 'container')]
    identity = read(EVIDENCE / 'runs/reference/container/identity.json')
    receipt = read(EVIDENCE / 'runs/reference/container/build-receipt.json')
    targets = [line.strip() for line in (ROOT / '.credproof/targets.txt').read_text(encoding='utf-8').splitlines()
               if line.strip() and not line.startswith('#')]
    return {
        'schema': 'credproof.ci-demo/v1',
        'source': {'evidence': 'docs/integration/evidence/ci-c', 'results_sha256': sha(EVIDENCE / 'results.json'),
                   'program_source_commit': results['program_source_commit'], 'anchors_commit': results['anchors_commit'],
                   'workflow_sha256': sha(ROOT / '.github/workflows/credproof.yml')},
        'environment': {'runner': 'GitHub 托管 ubuntu-24.04 虚拟机', 'kernel': identity.get('kernel'),
                        'python': (identity.get('python') or '').split(' ')[0],
                        'base_image_digest': (receipt.get('base_image') or {}).get('digest'),
                        'jobs': {'native': '直接在 Linux 上准备运行时并检查（不用 Docker）',
                                 'container': '从同一提交构建镜像，在容器内检查'}},
        'workflow': {'trigger': 'pull_request（只针对配置的目标分支）',
                     'permissions': ['contents: read', 'security-events: write'],
                     'targets': targets,
                     'steps': ['检出代码', '准备运行时或构建镜像', 'doctor 自检隔离环境', '逐个配置运行 check',
                               '上传报告、JUnit、摘要和 SARIF', '按退出码判定是否放行'],
                     'sarif_upload': '仅 container job 上传到代码扫描；native 的 SARIF 作为构件保存'},
        'exit_codes': [{'code': 0, 'meaning': '通过'}, {'code': 2, 'meaning': '不通过'},
                       {'code': 3, 'meaning': '证据不足（按不通过处理）'}, {'code': 4, 'meaning': '配置、参数或环境错误'}],
        'controls': controls,
        'acceptance': {
            'anchors': {'expected': 16, 'native': rows[('reference', 'native')]['anchors_matched'],
                        'container': container['anchors_matched']},
            'default_container': {'doctor_exit': container['default_doctor_exit'],
                                  'check_exit': container['default_check_exit'],
                                  'check_verdict': container['default_check_verdict']},
            'image_scan': {'completed': container['image_scan_completed'], 'files': container['image_files'],
                           'bytes': container['image_bytes'], 'unexempted_hits': container['image_sensitive_hits'],
                           'reviewed_matches': container['reviewed_pattern_matches']},
            'model_calls': results['model_calls'],
            'apparmor': '容器以显式选择的外层 AppArmor unconfined 方式运行，并为固定 bwrap 加载 userns 例外；限定版 AppArmor profile 尚未验收。',
        },
        'limits': '只覆盖已适配配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务；两条演示只证明闸门给出一红一绿，不代表全项目安全。',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='fail if the committed file differs')
    args = parser.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=1) + '\n'
    hits = FORBIDDEN.findall(text)
    if hits:
        raise SystemExit(f'refuse: forbidden content in derived file: {sorted(set(hits))}')
    if args.check:
        raise SystemExit(0 if OUTPUT.read_text(encoding='utf-8') == text else 'ci-demo.json is stale')
    OUTPUT.write_text(text, encoding='utf-8', newline='\n')
    print(f'wrote {OUTPUT.relative_to(ROOT)} ({len(text.encode())} bytes)')


if __name__ == '__main__':
    main()
