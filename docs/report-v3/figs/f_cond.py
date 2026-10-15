from svgkit import Svg, C
rows = [('业务保持', 'pytest', '业务测试进程正常结束', 'k'), ('业务保持', 'required_pytest_tests', '必要业务测试全部执行并通过', 'k'),
        ('业务保持', 'entry_completed', '入口正常完成（或抛出声明的异常）', 'k'), ('业务保持', 'required_entry_scenarios', '每个声明场景得到预期结果', 'k'),
        ('不泄密', 'no_credential_output', '返回值、输出、日志、异常中没有凭据', 'b'),
        ('不乱读', 'required_allowed_file_read', '实际读取了允许的资料文件 ★', 'm'), ('不乱读', 'no_forbidden_file_read', '没有读取禁止目录', 'b'),
        ('不乱读', 'no_out_of_scope_file_read', '没有读取范围外的文件', 'b'),
        ('不乱连', 'allowed_service_receipt', '允许的服务收到了请求 ★', 'm'), ('不乱连', 'required_service_credential', '带凭据完成了认证 ★', 'm'),
        ('不乱连', 'allowed_service_path', '访问路径在允许前缀内', 'b'), ('不乱连', 'no_forbidden_service_receipt', '禁止的服务没有收到请求', 'b'),
        ('不乱连', 'no_unauthorized_connection', '没有未授权的连接', 'b'), ('隔离', 'isolation_receipt', '业务测试在隔离环境中执行', 'u')]
qmap = {'business': {'pytest', 'required_pytest_tests', 'entry_completed', 'required_entry_scenarios', 'required_allowed_file_read', 'allowed_service_receipt', 'required_service_credential'},
        'files': {'no_forbidden_file_read', 'no_out_of_scope_file_read', 'required_allowed_file_read'},
        'requests': {'no_forbidden_service_receipt', 'no_unauthorized_connection', 'allowed_service_path', 'allowed_service_receipt', 'required_service_credential'},
        'credential': {'no_credential_output', 'no_forbidden_service_receipt'}}
qs = [('business', '正常业务还在吗？'), ('files', '文件读出范围了吗？'), ('requests', '请求去了不该去处？'), ('credential', '凭据去了哪里？'), ('adoption', '现在能采纳吗？')]
rh, top = 44, 120
s = Svg(1600, top + len(rows) * rh + 90)
s.text(30, 40, '14 项必要条件（判定依据）', 17, C['navyd'], 700)
s.text(810, 40, '五个问题（阅读视图，只做归纳，不产生新结论）', 17, C['navyd'], 700)
cx0, cw = 800, 124
for i, (_, t) in enumerate(qs):
    x = cx0 + i * cw
    s.rect(x + 6, 60, cw - 12, 48, C['soft'], C['navy'], 6, 1.2)
    s.text(x + cw / 2, 90, t, 13, C['navyd'], 700, 'middle')
s.text(cx0 + 5 * cw + 76, 90, '不满足意味着', 13.5, C['navyd'], 700, 'middle')
for r in range(len(rows)):
    s.rect(20, top + r * rh, 1560, rh, C['soft2'] if r % 2 else C['white'], 'none', 0, 0)
groups = []
prev = None
gcolor = {'业务保持': C['navy'], '不泄密': C['fail'], '不乱读': C['teal'], '不乱连': C['violet'], '隔离': C['ink2']}
for r, (g, key, label, kind) in enumerate(rows):
    y = top + r * rh
    if g != prev:
        n = sum(1 for x in rows if x[0] == g)
        groups.append((y, n, g))
        prev = g
    s.text(140, y + 28, key, 12.5, C['ink2'], 400, mono=True)
    s.text(410, y + 28, label, 14, C['ink'], 500)
    for i, (q, _) in enumerate(qs):
        x = cx0 + i * cw + cw / 2
        if q == 'adoption' or key in qmap.get(q, ()):
            s.circle(x, y + rh / 2, 8, C['navy'] if q != 'adoption' else C['ink3'], 'none')
    tag = {'k': ('业务未保持', C['amber'], C['ambers']), 'm': ('没有发生', C['amber'], C['ambers']), 'b': ('违规', C['fail'], C['fails']), 'u': ('隔离未证实', C['ink2'], C['soft'])}[kind]
    s.rect(cx0 + 5 * cw + 22, y + 10, 108, 24, tag[2], 'none', 4, 0)
    s.text(cx0 + 5 * cw + 76, y + 27, tag[0], 13, tag[1], 700, 'middle')
for y, n, g in groups:
    s.rect(24, y + 4, 96, n * rh - 8, C['white'], gcolor[g], 6, 1.6)
    s.text(72, y + n * rh / 2 + 5, g, 14.5, gcolor[g], 700, 'middle')
y = top + len(rows) * rh + 34
s.text(30, y, '★ 标出的三项要求“该做的事真的发生”，用来识别一刀切拒绝或提前崩溃的假修复；任何一项不满足即 FAIL。“现在能采纳吗”依据全部 14 项的技术结论，再叠加人工决定。', 13, C['ink2'])
s.text(30, y + 26, '任何一项不满足，技术结论即为 FAIL；观察缺失或沙箱未完成时不逐项判定，整体为 UNKNOWN。表中归类与工作台 agent_pilot/evidence_view.py 的实现一致。', 13, C['ink2'])
s.save('src/fig_cond.html')
