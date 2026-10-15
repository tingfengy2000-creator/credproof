from svgkit import Svg, C
s = Svg(1600, 1000)
cols = [('工作台服务', 130, C['navy']), ('检查器 check_project', 390, C['pass_']), ('bubblewrap 沙箱', 680, C['fail']),
        ('被测项目代码', 950, C['ink2']), ('审计钩子', 1200, C['fail']), ('模拟服务（允许/禁止）', 1440, C['fail'])]
for name, x, col in cols:
    s.box(x - 110, 20, 220, 50, name, [], C['white'], col, col, 15)
    s.line(x, 70, x, 975, C['rule'], 1.4, '5 5')
s.rect(560, 210, 1010, 520, 'none', C['fail'], 8, 1.6, '8 5')
s.text(572, 232, '沙箱内：只读 rootfs · 独立命名空间（仅回环）· 能力全部丢弃 · 资源限制', 12.5, C['fail'], 700)
def msg(y, x1, x2, t, color=None, dash=None, sub=None):
    s.arrow([(x1, y), (x2, y)], color or C['ink2'], 1.6, dash)
    s.text((x1 + x2) / 2, y - 8, t, 13, color or C['ink'], 600, 'middle')
    if sub:
        s.text((x1 + x2) / 2, y + 18, sub, 11.5, C['ink2'], 400, 'middle')
def self_(y, x, t, color=None, sub=None, w=None):
    s.add(f'<path d="M{x},{y} L{x + 40},{y} L{x + 40},{y + 22} L{x + 4},{y + 22}" fill="none" stroke="{color or C["ink2"]}" stroke-width="1.5" marker-end="url(#a0)"/>')
    s.text(x + 50, y + 8, t, 12.5, color or C['ink'], 600)
    if sub:
        s.text(x + 50, y + 26, sub, 11.5, C['ink2'])
def step(y, x, n):
    s.circle(x - 16, y - 4, 10, C['navyd'], C['navyd'])
    s.text(x - 16, y + 0.5, str(n), 11, '#FFFFFF', 700, 'middle')
msg(105, 130, 390, '① 检查（附期望版本/对象/报告摘要）', C['navy'])
self_(125, 390, '② 复制项目到一次性目录', C['pass_'], '生成本次合成凭据；建允许/禁止目录')
msg(190, 390, 680, '③ 启动 bwrap（--unshare-all · 只读绑定）', C['pass_'])
self_(250, 680, '④ 安装审计钩子与访问策略', C['fail'], '启动允许 / 禁止两个模拟服务')
msg(320, 680, 950, '⑤ 运行必要业务测试（pytest）', C['fail'])
msg(380, 950, 1200, '⑥ open / connect 尝试', C['ink2'], None, '动作发生前记录：允许 · 禁止 · 范围外')
msg(450, 950, 1440, '⑦ HTTP 请求（带认证头）', C['ink2'], None, '回执：服务 · 路径 · 凭据是否正确')
msg(500, 1440, 950, '/api/redirect → 302 指向禁止服务', C['fail'], '6 4')
msg(570, 680, 950, '⑧ 按每个声明场景调用入口函数', C['fail'], None, '占位符替换为允许文件、跳转地址等')
msg(640, 950, 680, '返回值 / 异常 / 输出 / 日志', C['ink2'], '6 4')
msg(700, 680, 390, '⑨ 观察记录（测试 · 场景 · 请求 · 审计事件 · 输出）', C['fail'], '6 4')
self_(760, 390, '⑩ 在输出、日志、返回值、异常中匹配合成凭据', C['pass_'], '计算 14 项必要条件；报告脱敏')
msg(850, 390, 130, '⑪ 报告：PASS / FAIL / UNKNOWN', C['navy'], '6 4', '工作台派生五个问题、SARIF、JUnit')
s.rect(150, 890, 1300, 70, C['ambers'], C['amber'], 8, 1.4, '6 4')
s.text(170, 918, 'alt  沙箱建不起来 / 观察不完整 / 必要测试未执行', 13.5, C['amber'], 700)
s.text(170, 944, '直接返回 UNKNOWN（退出码 3），不在宿主机降级执行，也不推断为通过', 13, C['ink'])
s.save('src/fig_seq.html')
