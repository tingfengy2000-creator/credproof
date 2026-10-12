# PR #8 follow-up: documentation checked, browser checks blocked

被审 head：`79e6b74627b4001ac071bd831d4133c1ccb10c8a`，分支 `feat/console-ui`。本轮在独立 review worktree 核对；不修改原研发工作区、main、冻结基线或 PR 源分支，不合并任何 PR。

## 本轮结论

- **旧启动文档问题关闭。** UI README 已改成 `view/recheck/live`；核对了真实 `launch.main`、`Application`、HTTP Handler、ReviewWorkspace 和 ProjectWorkspace。view 拒绝动态 `/check`、项目检查和案例复检；保存修订、记录决定、导出文件没有模式级禁用。它们仍需通过会话、当前版本/材料及各自的审批/导出条件，并非任意对象都能成功。
- **live 启动说明准确。** `launch_command` 从显式 `CREDPROOF_INSTALLED_PYTHON` 或集中配置的 `program_python` 取绝对解释器路径，构造 `-I -m credproof_safety.web_repair`。缺失/无效时拒绝，不回退旧 `_runs` 或 `offline_run`。页面初始化和查看不发起新推理；没有在本轮点击模型启动按钮。
- **42 项软件/HTTP 协议回归通过，exit 0。** 覆盖 web、bench HTTP、人工审阅状态、启动配置和三模式门禁。测试中的执行器、报告或子进程替身已由原测试明确标识；不是新安全实验、真实人工采纳或手动浏览器检查。[stdout](protocol-pytest.txt)、[JUnit](protocol-pytest.xml)、[命令/计数/摘要](source-and-checks.json)。
- `node --check` 对 `app.js` 和新增 `check-console.mjs` 均 exit 0；`test_ui_project_verdict.js` exit 0，输出 `ui-project-verdict-regression: PASS (FAIL/PASS/stale/missing cases)`。
- 新提交仅改 UI README 与新增浏览器脚本。执行器、HTML/CSS/JS、只读查看入口均与上一被审 head 相同；摘要见 [来源核对](source-and-checks.json)。上一轮 255 项 Windows 软件测试、6 项安装版只读 HTTP 测试继续作为其对应版本的证据，**没有称为本轮重跑**：[前次固定证据](https://github.com/tingfengy2000-creator/credproof/blob/9e5b8ad4a1a90e60202437acd73b5b28cb4361a8/docs/review/pr-8-console-windows/README.md)。

## 浏览器检查状态和脚本覆盖范围

本轮浏览器工具三次拒绝 `http://127.0.0.1:8768/#overview`，其中两次分别在用户回复“已清除”和“已移除”后重试；原文：`A saved user permission setting blocks this action.` 工具同时明确禁止用间接执行、替代浏览器或原始 CDP 绕过。只读核对到本机 `config.toml` 对该精确 origin 已有 `access="allow"`，但不能由此宣布实际工具许可已经生效。没有修改权限配置，没有运行 Playwright/Edge 脚本，不另换端口或驱动来完成被拒绝的浏览器动作。[本轮权限观察](browser-permission-observation.json)。

因此本轮 **未生成浏览器 summary.json、截图或 report.pdf**，未完成 Windows 字体/矩阵/路由/打印、recheck 模式实际按钮与跨页面 409 提示、live 按钮可用状态核验。现有软件/HTTP 检查不补写为这些项目已通过。新增模型调用、真实候选执行、真实采纳和动态导出复检均为 0。

对新增脚本的静态审查发现，脚本 PASS 不能直接等同所有先前浏览器验收项通过：

1. `check-console.mjs:55-59` 记录字体宽度启发式结果，未将所需 Windows 中文字体缺失加入 failures。应明确最低字体条件，或将其列为需要阅读结果的人工项。
2. `:60-65,73` 仅在矩阵出现时比较已有表头与行的 x 坐标；没有要求 overview 矩阵存在，也没有断言 67 列/必要方法行数。矩阵缺失或列数减少而位置一致时可漏报。请按当前评测对象数断言，避免把空矩阵当对齐通过。
3. 脚本访问 b07 路由，但只检查可见视图，没有断言“不通过”、与漏洞原版相同及空差异；须增加对应断言或明确保留人工核验。
4. 生成 A4 PDF 和截图后仍需查看实际页面；字体宽度、DOM 坐标和打印导航检查不能代替对字形、裁切与分页的目视检查。本轮未声称完成此项。

脚本仅做语法与源码审查，未产生它的浏览器运行结论。请 5060 在同一 PR 追加上述必要检查或收窄脚本 PASS 的说明，不改安全检查器或新增模型任务。

## 文件与接口依据

- [三种模式说明](../../../agent_pilot/ui/README.md)
- [浏览器检查脚本](../../ui/console-v1/check-console.mjs)
- [CLI 模式选择](../../../agent_pilot/launch.py)
- [启动、模式门禁与 HTTP 接口](../../../agent_pilot/web.py)
- [人工修订/决定/导出及版本绑定](../../../credproof_safety/human_review.py)
- [项目检查与导出](../../../agent_pilot/project_workspace.py)
- [严格只读 GET 入口](../../handoff/frontend-5060/view-readonly.py)

真实字段仍由前端发送：`expected={version_id,object_sha256,report_sha256,decision_count}`、`X-CredProof-Review-Session`；后端拒绝旧对象。源码核对和协议测试不代表本轮已经点击页面验证冲突提示。

## 命令与合并安排

```powershell
# 独立 worktree，已有软件测试环境；不调用模型/候选执行。
$env:TEMP='E:/比赛/CPUI8/tmp'; $env:TMP=$env:TEMP
$env:CREDPROOF_RUNTIME_TEMP=$env:TEMP
& 'E:/比赛/CP35/venv/Scripts/python.exe' -m pytest agent_pilot/tests/test_web.py agent_pilot/tests/test_web_bench.py agent_pilot/tests/test_human_review.py agent_pilot/tests/test_runtime_config.py agent_pilot/tests/test_delivery_modes.py -q -rs --junitxml=E:/比赛/CPUI8/followup-79e6b74/protocol-pytest.xml
# 42 passed / 0 failed / 0 skipped; exit 0
node --check docs/ui/console-v1/check-console.mjs
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
# exit 0 each
```

如果用户批准合并，当前叠加链应先向各自 base 汇入顶层变更：`#8 → #7 → #6 → #4 → #3`，最后 `#1` 合入项目主线 `feat/frontend-human-review-5060`。每步都要核对当时 head/base 与 REST 合并结果；**本轮没有执行合并**。main 不在这条项目主线内。本次没有重试或声称复现此前 GraphQL 403。

结论：**文档旧入口已更正；软件回归通过；浏览器和动态按钮验收仍阻断，待用户处理保存的站点拒绝并决定合并。** 本轮原日志保留，[脱敏/换行映射](derivation.json)给出独立派生摘要。
