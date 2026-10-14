"""Derive comparison/v1 from the frozen bench JSON only; no execution/network.

python scripts/compare/build_comparison.py [--check]
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT/'docs/bench/bench-results.json'
OUTPUT = ROOT/'docs/compare/comparison.json'
DESCRIPTIONS = {
 'ci': ('业务测试（CI 中的 pytest）', '已有业务断言是否通过',
        '断言未覆盖的输出、目录访问、请求与凭据去向', '项目必要业务测试与其执行环境', False,
        '可以。规范 CI 可运行 pytest，也可接入静态扫描和本项目的动态检查。'),
 'static': ('冻结的 Gitleaks/Bandit/Semgrep 凭据规则', '源码与已配置凭据规则的匹配',
            '本批规则未覆盖的运行时秘密值、文件与重定向行为；不代表静态工具的能力上限',
            '固定扫描器、规则与可读源码', False, '可以，扫描器可在规范 CI 中运行。'),
 'credproof': ('CredProof 的声明条件验收', '受控执行中的输出、文件、请求与必要业务条件',
               '未声明场景、未支持的观察通道与真实生产环境', '人工配置、适配入口、必要测试和隔离环境', False,
               '可以。本项目已实现 CI 接入；本行以自身观察分组，按定义一致，非独立准确率。'),
}


def outcome(row, method):
    if method == 'ci':
        v = row.get('ci', {}).get('verdict')
        return {'PASS':'ACCEPT','FAIL':'REJECT'}.get(v)
    if method == 'static':
        v = row.get('static')
        return ('REJECT' if v['credential_alert'] else 'ACCEPT') if isinstance(v, dict) and type(v.get('credential_alert')) is bool else None
    if method == 'credproof':
        return {'PASS':'ACCEPT','FAIL':'REJECT','UNKNOWN':'UNKNOWN'}.get(row['credproof'].get('verdict'))
    return row.get('judges', {}).get(method.removeprefix('judge:'), {}).get('verdict')


def denominators(rows):
    return {'total':len(rows), 'unsafe':sum(r['credproof']['verdict']=='FAIL' for r in rows),
            'good':sum(r['credproof']['verdict']=='PASS' for r in rows),
            'unknown':sum(r['credproof']['verdict'] not in ('PASS','FAIL') for r in rows)}


def metrics(rows, method):
    valid = [(r, outcome(r, method)) for r in rows]
    covered = [(r,v) for r,v in valid if v in ('ACCEPT','REJECT','INVALID','UNKNOWN')]
    bad = [(r,v) for r,v in covered if r['credproof']['verdict']=='FAIL']
    good = [(r,v) for r,v in covered if r['credproof']['verdict']=='PASS']
    # Keep the frozen summary's non-accept convention; INVALID is an overlapping
    # category and is explicitly split below, never silently removed.
    rejected = [r for r,v in good if v != 'ACCEPT']
    accepted = [r for r,v in bad if v == 'ACCEPT']
    illustrative = next(iter(accepted or rejected or [r for r,v in covered]), None)
    return {'accepted_unsafe':len(accepted), 'rejected_good':len(rejected),
            'explicit_rejected_good':sum(v=='REJECT' for r,v in good),
            'invalid':sum(v=='INVALID' for r,v in covered),
            'unknown':sum(v=='UNKNOWN' for r,v in covered), 'missing':len(rows)-len(covered),
            'coverage':{'rows':len(covered),'unsafe':len(bad),'good':len(good)},
            'example_patch_id':illustrative['id'] if illustrative else None,
            'example_route':'#patch/'+illustrative['id'] if illustrative else None}


def build(data, digest):
    if data['schema'] != 'credproof.bench-results/v1':raise ValueError('unsupported_frozen_schema')
    rows=data['patches']
    if len({r['id'] for r in rows}) != len(rows):raise ValueError('duplicate_patch_id')
    methods=['ci','static',*['judge:'+j for j in data['judges']],'credproof']
    descriptions=dict(DESCRIPTIONS)
    for judge in data['judges']:
        descriptions['judge:'+judge]=(judge+'（文本裁判）','输入源码、规则和测试的文本分析',
           '本次裁判不执行代码，模型解释不能代替请求回执或真实返回值',
           '固定本地模型、裁判提示和上下文',True,'可以编排模型裁判；仍需独立执行证据与权限边界。')
    batches=[('ai','同一冻结批次的全部 AI 补丁',lambda r:r['origin']['kind']=='ai'),
             ('anchors','漏洞原版与人工参考修复锚点',lambda r:r['origin']['kind'] in ('vulnerable','reference')),
             ('history','全部历史 AI 补丁的统一复检',lambda r:r['origin']['kind']=='history')]
    return {'schema':'credproof.comparison/v1','generated_from':[{'path':INPUT.relative_to(ROOT).as_posix(),'sha256':digest}],
      'denominators':{**denominators(rows),'note':'unsafe 沿用冻结表 FAIL 分组，含安全违规、业务破坏和过度拒绝，不全是漏洞；good=PASS；UNKNOWN 单列。每种方法有自己的覆盖分母，缺失不当放行或拒绝。'},
      'methods':[{'id':m,'label':descriptions[m][0],'observes':descriptions[m][1],
          'does_not_observe':descriptions[m][2],'needs':descriptions[m][3],'model_required':descriptions[m][4],
          'can_ci_do_this':descriptions[m][5],**metrics(rows,m)} for m in methods],
      'batches':[{'id':name,'label':label,'denominators':denominators(group),
          'methods':[{'id':m,**metrics(group,m)} for m in methods]}
          for name,label,select in batches for group in [[r for r in rows if select(r)]]],
      'honest_limits':['全部 88 记录保留，51 AI、16 锚点、21 历史分开；不同覆盖范围不可直接排总名次。',
          '样本是开发可见的合成小工具，不代表真实项目分布；本轮未重跑实验或模型。',
          'rejected_good 沿用冻结汇总的非放行口径（包含 INVALID）；invalid 为交叉计数，不可相加。explicit_rejected_good 只计明确 REJECT。',
          '静态方法只比较冻结 credential_alert 规则，不等于所有扫描器或数据流分析的能力上限。',
          'CredProof 分组依据就是自身受控观察与必要条件，本行按定义一致，不是独立盲测或整体准确率。',
          '规范 CI 可执行相同扫描、业务测试和隔离检查；区别在实际配置的规则与观察，不是有无 CI。'],
      'generator':'scripts/compare/build_comparison.py --check 可复算'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
    raw=INPUT.read_bytes();value=build(json.loads(raw),hashlib.sha256(raw).hexdigest())
    text=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if a.check:
        if not OUTPUT.is_file() or OUTPUT.read_text('utf8') != text:raise SystemExit('comparison.json is missing or stale')
    else:
        OUTPUT.parent.mkdir(parents=True,exist_ok=True);OUTPUT.write_text(text,encoding='utf8',newline='\n')
    print(json.dumps({'mode':'check' if a.check else 'generate','denominators':value['denominators']},ensure_ascii=False))

if __name__=='__main__':main()
