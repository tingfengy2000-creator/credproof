"""Data charts for the report. Every number is read from the frozen repo JSON."""
import json, sys, datetime as dt
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).parent / 'out'
OUT.mkdir(exist_ok=True)

C = dict(navy='#1E4D7A', navyd='#13233A', pass_='#2E7A57', fail='#B23A2E', amber='#9A6A0B',
         violet='#4D5591', teal='#1F6F78', grey='#8A94A3', line='#D5DCE5', ink='#23303F',
         passs='#DCEFE5', fails='#F6DEDA', ambers='#F5EAD2', navys='#DDE7F2', greys='#EEF1F5')
plt.rcParams.update({'font.family': 'Noto Sans CJK SC', 'font.size': 10.5, 'axes.edgecolor': C['line'],
                     'axes.labelcolor': C['ink'], 'xtick.color': C['ink'], 'ytick.color': C['ink'],
                     'axes.spines.top': False, 'axes.spines.right': False, 'savefig.dpi': 220,
                     'axes.unicode_minus': False})


def save(fig, name):
    fig.savefig(OUT / f'{name}.png', bbox_inches='tight', facecolor='white', pad_inches=0.12)
    plt.close(fig)


comp = json.loads((REPO / 'docs/compare/comparison.json').read_text())
LABEL = {'ci': '业务测试\n(CI pytest)', 'static': '冻结凭据规则\n(Gitleaks/Bandit/Semgrep)',
         'judge:qwen2.5-coder:32b-instruct-q4_K_M': 'Qwen2.5-Coder-32B\n文本裁判',
         'judge:qwen3-coder:30b': 'Qwen3-Coder-30B\n文本裁判', 'credproof': 'CredProof\n声明条件验收'}


# 1. Method comparison on all 88 records -----------------------------------
def chart_compare():
    ms = comp['methods']
    fig, axes = plt.subplots(1, 2, figsize=(8.4, 3.77), sharey=True, gridspec_kw={'wspace': 0.62})
    y = range(len(ms))[::-1]
    for ax, key, cov, title, col in (
            (axes[0], 'accepted_unsafe', 'unsafe', '放过不合格（越低越好）', C['fail']),
            (axes[1], 'rejected_good', 'good', '拦错合格（越低越好）', C['amber'])):
        for yi, m in zip(y, ms):
            n, d = m[key], m['coverage'][cov]
            ax.barh(yi, 1, color=C['greys'], height=0.58)
            ax.barh(yi, n / d if d else 0, color=C['pass_'] if n == 0 else col, height=0.58)
            txt = f'{n}/{d}'
            if m.get('missing'):
                txt += f'  (缺失 {m["missing"]})'
            if key == 'rejected_good' and m.get('invalid'):
                txt += f'  含无效 {m["invalid"]}'
            ax.text(1.03, yi, txt, va='center', fontsize=9.5, color=C['ink'])
        ax.set_yticks(list(y), [LABEL[m['id']] for m in ms], fontsize=9)
        if ax is axes[1]:
            ax.tick_params(labelleft=False)
        ax.set_xlim(0, 1); ax.set_xticks([0, .5, 1], ['0', '50%', '100%'])
        ax.set_title(title, fontsize=11, color=C['navyd'], loc='left', pad=8)
        ax.tick_params(axis='y', length=0)
    fig.text(0.01, -0.07, '分母：不合格 34、合格 53、UNKNOWN 1 单列；两个文本裁判缺失 21 条历史记录，按各自覆盖分母计算。\n'
             'CredProof 一行按自身观察分组，属于定义一致性，不是独立准确率。', fontsize=9, color=C['grey'], linespacing=1.4)
    save(fig, 'chart_compare')


# 2. AI batch: 51 patches waffle + 6 unsafe x methods --------------------
def chart_ai():
    bench = json.loads((REPO / 'docs/bench/bench-results.json').read_text())
    ai = [p for p in bench['patches'] if p['origin']['kind'] == 'ai']
    targets = [t['id'] for t in bench['targets']]
    names = {t['id']: t['title']['zh'] for t in bench['targets']}
    fig = plt.figure(figsize=(8.4, 3.96))
    ax = fig.add_axes([0.0, 0.08, 0.46, 0.82])
    rows = {t: [p for p in ai if p['target'] == t] for t in targets}
    for i, t in enumerate(targets):
        yi = len(targets) - 1 - i
        for j, p in enumerate(rows[t]):
            ok = p['credproof']['verdict'] == 'PASS'
            ax.add_patch(FancyBboxPatch((j + 0.1, yi + 0.12), 0.8, 0.76, boxstyle='round,pad=0,rounding_size=0.14',
                                        fc=C['passs'] if ok else C['fail'], ec=C['pass_'] if ok else C['fail'], lw=0.9))
        ax.text(-0.25, yi + 0.5, f'{t[:3].upper()} {names[t]}', ha='right', va='center', fontsize=9.2)
    width = max(len(v) for v in rows.values())
    ax.set_xlim(-2.6, width + 0.2); ax.set_ylim(-0.1, len(targets) + 0.1); ax.axis('off')
    s = bench['summary']['ai']
    ax.set_title(f'同一冻结批次 {s["patches"]} 个 AI 补丁：CI 全绿 {s["ci_green"]}，CredProof 判 FAIL {s["credproof"]["FAIL"]}',
                 fontsize=10.5, color=C['navyd'], loc='left')
    ax.add_patch(Rectangle((0.1, -0.75), 0.5, 0.4, fc=C['passs'], ec=C['pass_'], clip_on=False))
    ax.text(0.75, -0.55, 'PASS', va='center', fontsize=8.5)
    ax.add_patch(Rectangle((2.2, -0.75), 0.5, 0.4, fc=C['fail'], ec=C['fail'], clip_on=False))
    ax.text(2.85, -0.55, 'FAIL（凭据随跳转发往未授权服务）', va='center', fontsize=8.5)

    bx = fig.add_axes([0.56, 0.08, 0.44, 0.82])
    bad = [p for p in ai if p['credproof']['verdict'] != 'PASS']
    cols = ['业务测试', '凭据规则', 'Qwen2.5\n裁判', 'Qwen3\n裁判', 'CredProof']
    for i, p in enumerate(bad):
        yi = len(bad) - 1 - i
        verdicts = [p['ci']['verdict'] == 'PASS', not p['static']['credential_alert'],
                    p['judges']['qwen2.5-coder:32b-instruct-q4_K_M']['verdict'] == 'ACCEPT',
                    p['judges']['qwen3-coder:30b']['verdict'] == 'ACCEPT', p['credproof']['verdict'] == 'PASS']
        for j, accepted in enumerate(verdicts):
            bx.add_patch(FancyBboxPatch((j + 0.08, yi + 0.12), 0.84, 0.76, boxstyle='round,pad=0,rounding_size=0.12',
                                        fc=C['fails'] if accepted else C['passs'], ec=C['fail'] if accepted else C['pass_'], lw=1))
            bx.text(j + 0.5, yi + 0.5, '放行' if accepted else '拦截', ha='center', va='center', fontsize=9,
                    color=C['fail'] if accepted else C['pass_'], weight='bold')
        o = p['origin']
        bx.text(-0.12, yi + 0.5, f'B07 s{o["sample"]}·r{o["round"]}', ha='right', va='center', fontsize=8.8)
    for j, c in enumerate(cols):
        bx.text(j + 0.5, len(bad) + 0.12, c, ha='center', va='bottom', fontsize=8.8, color=C['navyd'])
    bx.set_xlim(-1.3, len(cols)); bx.set_ylim(-0.1, len(bad) + 1.0); bx.axis('off')
    bx.set_title('6 个不合格补丁在各方法下的结论', fontsize=10.5, color=C['navyd'], loc='left', pad=14)
    save(fig, 'chart_ai')


# 3. Material assistant: 3 versions x 5 questions --------------------------
def chart_case():
    src = (REPO / 'agent_pilot/ui/app.js').read_text()
    blob = src.split('// STORY_EVIDENCE_BEGIN')[1].split('// STORY_EVIDENCE_END')[0]
    story = json.loads(blob.split('=', 1)[1].strip().rstrip(';'))
    vers = [('original', '原问题'), ('v000', 'AI 候选 v000'), ('v001', '开发者修订 v001')]
    qs = [('business', '业务是否正常'), ('files', '文件是否越界'), ('requests', '请求去了哪里'),
          ('credential', '凭据出现在哪里'), ('adoption', '能否采用')]
    style = {'ok': (C['passs'], C['pass_'], '正常'), 'bad': (C['fails'], C['fail'], '违规/不可采用'),
             'missing': (C['ambers'], C['amber'], '未发生/待定'), 'unknown': (C['greys'], C['grey'], '未知')}

    def fact(v, q):
        f = {x['id']: x for x in story[v]['questions']}[q]['facts']
        if q == 'business':
            s = f'测试 {f["tests_passed"]}/{f["tests_required"]} 通过'
            return s + ('\n入口 ' + f['entry_error']['type'] if f['entry_error'] else f'\n授权读 {f["allowed_reads"]} 次')
        if q == 'files':
            return f'授权 {f["allowed_reads"]}  禁止 {f["forbidden_reads"]}' + ('\n' + f['forbidden_paths'][0] if f['forbidden_paths'] else '')
        if q == 'requests':
            return f'允许 {f["allowed"]}  禁止 {f["forbidden"]}\n越权连接 {f["unauthorized_connections"]}'
        if q == 'credential':
            ch = f['output_channels']
            cn = {'logs': '日志', 'return': '返回值', 'stdout': 'stdout', 'stderr': '标准错误'}
            return (f'输出泄露 {len(ch)} 处\n' + '/'.join(cn.get(c, c) for c in ch) if ch else '无输出泄露') + f'\n发往禁止服务 {f["sent_to_forbidden"]}'
        tr = {'PENDING': '待审', 'REJECTED': '已驳回', 'APPROVED': '已批准'}
        return f'{f["technical"]} · {tr.get(f["decision"], f["decision"])}\n未写回原件'
    fig, ax = plt.subplots(figsize=(8.4, 3.31))
    W, H = 1.9, 1.0
    for i, (v, vl) in enumerate(vers):
        yi = len(vers) - 1 - i
        ax.text(-0.15, yi * H + 0.5, vl, ha='right', va='center', fontsize=9.6, color=C['navyd'])
        vd = story[v]['verdict']
        ax.text(-2.7, yi * H + 0.5, vd, ha='center', va='center', fontsize=9, weight='bold', color='white',
                bbox=dict(boxstyle='round,pad=0.3', fc=C['pass_'] if vd == 'PASS' else C['fail'], ec='none'))
        for j, (q, ql) in enumerate(qs):
            st = {x['id']: x for x in story[v]['questions']}[q]['state']
            fc, ec, _ = style[st]
            ax.add_patch(FancyBboxPatch((j * W + 0.05, yi * H + 0.07), W - 0.1, H - 0.14,
                                        boxstyle='round,pad=0,rounding_size=0.06', fc=fc, ec=ec, lw=1))
            ax.text(j * W + W / 2, yi * H + 0.5, fact(v, q), ha='center', va='center', fontsize=7.9, color=C['ink'],
                    linespacing=1.35)
    for j, (q, ql) in enumerate(qs):
        ax.text(j * W + W / 2, len(vers) * H + 0.12, ql, ha='center', va='bottom', fontsize=10, color=C['navyd'], weight='bold')
    for k, (st, (fc, ec, lab)) in enumerate([(s, style[s]) for s in ('ok', 'missing', 'bad')]):
        ax.add_patch(Rectangle((k * 2.2, -0.45), 0.28, 0.22, fc=fc, ec=ec, clip_on=False))
        ax.text(k * 2.2 + 0.38, -0.34, lab, va='center', fontsize=8.6)
    ax.set_xlim(-3.05, len(qs) * W + 0.05); ax.set_ylim(-0.55, len(vers) * H + 0.5); ax.axis('off')
    save(fig, 'chart_case')


# 4. External component python-dotenv: 4 versions --------------------------
def chart_dotenv():
    d = json.loads((REPO / 'docs/compare/onboarding-dotenv.json').read_text())
    lab = {'before': '导入问题版', 'after': '人工修复', 'reintroduced_defect': '重新引入缺陷', 'unrelated_change': '无关注释修改'}
    rows = d['results']
    conds = ['pytest', 'required_pytest_tests', 'required_entry_scenarios', 'no_forbidden_file_read', 'no_credential_output']
    cl = ['上游+适配测试', '必要测试', '必要入口场景', '未读禁止文件', '凭据未输出']
    fig, ax = plt.subplots(figsize=(8.4, 3.04))
    for i, r in enumerate(rows):
        x = i * 2.55
        vd = r['verdict']
        ax.add_patch(FancyBboxPatch((x, 5.55), 2.3, 0.9, boxstyle='round,pad=0,rounding_size=0.12',
                                    fc=C['pass_'] if vd == 'PASS' else C['fail'], ec='none'))
        ax.text(x + 1.15, 6.17, f'{r["version"]} {lab[r["case"]]}', ha='center', va='center', color='white', fontsize=9.6, weight='bold')
        pt = r['pytest']
        ax.text(x + 1.15, 5.8, f'{vd} · pytest {pt["passed"]}/{pt["collected"]}', ha='center', va='center', color='white', fontsize=8.6)
        for k, c in enumerate(conds):
            bad = c in r['failed_conditions']
            yk = 4.6 - k * 0.95
            ax.add_patch(FancyBboxPatch((x, yk), 2.3, 0.78, boxstyle='round,pad=0,rounding_size=0.08',
                                        fc=C['fails'] if bad else C['passs'], ec=C['fail'] if bad else C['pass_'], lw=0.9))
            ax.text(x + 1.15, yk + 0.39, ('× ' if bad else '✓ ') + cl[k], ha='center', va='center', fontsize=8.8,
                    color=C['fail'] if bad else C['pass_'])
    ax.annotate('', xy=(2.55 * 3 + 2.3, 5.1), xytext=(2.55 * 3 + 2.3, 5.1))
    ax.set_xlim(-0.1, 2.55 * 4); ax.set_ylim(0.6, 6.55); ax.axis('off')
    save(fig, 'chart_dotenv')


# 5. CI matrix -------------------------------------------------------------
def chart_ci():
    d = json.loads((REPO / 'docs/integration/evidence/ci-c/results.json').read_text())
    rows = d['rows']
    cols = ['技术结论', '退出码', '业务必要测试', '入口场景', '证据锚点', '敏感信息命中']
    fig, ax = plt.subplots(figsize=(8.4, 2.48))
    order = sorted(rows, key=lambda r: (r['control'] != 'vulnerable', r['environment']))
    names = {'vulnerable': '含缺陷 PR', 'reference': '参考修复 PR'}
    envs = {'native': 'Runner 原生', 'container': '加固容器'}
    W = 1.55
    for i, r in enumerate(order):
        yi = len(order) - 1 - i
        ax.text(-0.1, yi + 0.5, f'{names[r["control"]]} · {envs[r["environment"]]}', ha='right', va='center', fontsize=9.4)
        vals = [r['verdict'], str(r['check_exit_code']), '通过' if r['business_required_passed'] else '未通过',
                f'{r["entry_scenarios"]} 个', f'{r["anchors_matched"]}/16',
                f'{r["formats_sensitive_hits"]}' + (f'（镜像 {r["image_sensitive_hits"]}）' if 'image_sensitive_hits' in r else '')]
        for j, v in enumerate(vals):
            good = not (j in (0, 1) and r['verdict'] == 'FAIL')
            fc = C['passs'] if good else C['fails']
            ec = C['pass_'] if good else C['fail']
            ax.add_patch(FancyBboxPatch((j * W + 0.04, yi + 0.1), W - 0.08, 0.8, boxstyle='round,pad=0,rounding_size=0.08', fc=fc, ec=ec, lw=0.9))
            ax.text(j * W + W / 2, yi + 0.5, v, ha='center', va='center', fontsize=9, color=C['ink'], weight='bold' if j < 2 else 'normal')
    for j, c in enumerate(cols):
        ax.text(j * W + W / 2, len(order) + 0.1, c, ha='center', va='bottom', fontsize=9.4, color=C['navyd'], weight='bold')
    ax.set_xlim(-3.0, len(cols) * W); ax.set_ylim(-0.05, len(order) + 0.6); ax.axis('off')
    save(fig, 'chart_ci')


# 6. Gantt -----------------------------------------------------------------
def chart_gantt():
    D = lambda s: dt.date.fromisoformat(s)
    tasks = [
        ('问题定位与方案设计', '2026-09-28', '2026-09-29', 'plan', '冻结威胁模型与 14 项条件'),
        ('隔离检查器与基准冻结', '2026-09-29', '2026-09-30', 'core', 'original6 / holdout8 离线实验'),
        ('外部回归与观察器修正', '2026-10-03', '2026-10-04', 'core', '外部组件 dotenv 场景 v1–v5'),
        ('候选增强与模型边界', '2026-10-05', '2026-10-07', 'exp', 'Agent 效果与跳转返回值'),
        ('有界补丁与编码模型对比', '2026-10-09', '2026-10-10', 'exp', '人工审核与版本绑定'),
        ('Bench v1 与 CI 集成', '2026-10-12', '2026-10-12', 'exp', '88 条记录 / 原生与容器作业'),
        ('产品化前端与 Windows 交付', '2026-10-12', '2026-10-14', 'prod', '接入向导、复检、对比、提案'),
        ('作品报告与演示材料', '2026-10-15', '2026-10-18', 'doc', '报告、演示视频、最终打包'),
    ]
    color = {'plan': C['grey'], 'core': C['navy'], 'exp': C['teal'], 'prod': C['violet'], 'doc': C['amber']}
    start = D('2026-09-27'); end = D('2026-10-19')
    fig, ax = plt.subplots(figsize=(8.4, 3.40))
    for i, (name, a, b, k, note) in enumerate(tasks):
        yi = len(tasks) - 1 - i
        x0 = (D(a) - start).days; w = (D(b) - D(a)).days + 1
        ax.add_patch(FancyBboxPatch((x0 + 0.06, yi + 0.2), w - 0.12, 0.6, boxstyle='round,pad=0,rounding_size=0.18',
                                    fc=color[k], ec='none', alpha=0.95 if k != 'doc' else 0.75))
        ax.text(x0 + w + 0.25, yi + 0.5, note, va='center', fontsize=8.5, color=C['grey'])
        ax.text(-0.3, yi + 0.5, name, ha='right', va='center', fontsize=9.4)
    days = (end - start).days
    for t in range(0, days + 1, 2):
        d = start + dt.timedelta(days=t)
        ax.axvline(t, color=C['line'], lw=0.6, zorder=0)
        ax.text(t, len(tasks) + 0.15, f'{d.month}/{d.day}', ha='center', fontsize=8.2, color=C['ink'])
    ax.set_xlim(0, days); ax.set_ylim(0, len(tasks) + 0.6); ax.axis('off')
    save(fig, 'chart_gantt')


if __name__ == '__main__':
    which = sys.argv[1:] or ['compare', 'ai', 'case', 'dotenv', 'ci', 'gantt']
    for w in which:
        globals()['chart_' + w]()
        print('ok', w)
