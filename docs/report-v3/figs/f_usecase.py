from svgkit import Svg, C
s = Svg(1600, 860)
s.rect(300, 30, 1000, 800, C['soft2'], C['navyd'], 14, 1.8)
s.text(800, 66, '密证 CredProof 工作台与检查器', 18, C['navyd'], 700, 'middle')
uc = {}
def u(key, cx, cy, t, color=None, fill=None, rx=150):
    uc[key] = (cx, cy, rx)
    s.ellipse(cx, cy, rx, 34, fill or C['white'], color or C['navy'], 1.6)
    s.text(cx, cy + 6, t, 15, C['ink'], 600, 'middle')
u('intake', 520, 140, '接入项目（上传 / 示例）')
u('config', 520, 230, '填写并冻结验收配置')
u('check', 520, 330, '运行隔离检查', C['pass_'], C['passs'])
u('read', 520, 430, '阅读证据：五个问题')
u('revise', 520, 530, '修订入口代码')
u('decide', 520, 650, '做出采纳决定')
u('judge', 1060, 250, '按 14 项条件判定', C['pass_'], C['passs'], 140)
u('ai', 1060, 530, '请求本地模型候选', C['violet'], C['violets'], 140)
u('bind', 1060, 650, '核对期望对象（版本·报告）', C['navy'], None, 160)
u('export', 520, 760, '导出已采纳修复', C['teal'], C['teals'], 140)
u('recheck', 1060, 760, '复检导出包（重新执行同一判定）', C['teal'], C['teals'], 170)
u('ci', 1060, 140, '在 PR 上运行检查', C['ink2'], None, 140)
u('fmt', 1060, 380, '下载 SARIF / JUnit / 摘要', C['ink2'], None, 160)
s.actor(130, 230, '开发者')
s.actor(130, 600, '审阅负责人')
s.actor(1470, 140, 'CI 流水线')
s.actor(1470, 500, '本地模型\n（可选）', C['violet'])
s.actor(1470, 730, '复检方 / 审计', C['teal'])
def link(a, key, color=None):
    cx, cy, rx = uc[key]
    ax, ay = a
    x = cx - rx if ax < cx else cx + rx
    s.line(ax, ay, x, cy, color or C['ink2'], 1.4)
for k in ('intake', 'config', 'check', 'read', 'revise'):
    link((165, 225), k)
for k in ('read', 'decide', 'export'):
    link((165, 595), k)
link((1435, 135), 'ci'); link((1435, 145), 'fmt')
link((1435, 495), 'ai', C['violet'])
link((1435, 725), 'recheck', C['teal'])
def rel(a, b, label, color=None):
    (ax, ay, arx), (bx, by, brx) = uc[a], uc[b]
    x1 = ax + arx if bx > ax else ax - arx
    x2 = bx - brx if bx > ax else bx + brx
    if abs(bx - ax) < 10:
        x1 = x2 = ax; ay += 34; by -= 34
    s.arrow([(x1, ay), (x2, by)], color or C['ink3'], 1.3, '6 4', label=label, lsize=12)
rel('check', 'judge', '«include»', C['pass_'])
rel('ci', 'judge', '«include»', C['pass_'])
rel('ai', 'revise', '«extend»', C['violet'])
rel('decide', 'bind', '«include»')
rel('read', 'fmt', '«extend»')
s.arrow([(520, 684), (520, 724)], C['teal'], 1.3, '6 4', label='仅 PASS 且已采纳', lx=600, ly=710, lsize=12)
s.text(800, 818, '«include» 必然包含   «extend» 条件扩展   彩色用例：判定（绿）· 模型（紫）· 导出复检（青）', 12.5, C['ink2'], 400, 'middle')
s.save('src/fig_usecase.html')
