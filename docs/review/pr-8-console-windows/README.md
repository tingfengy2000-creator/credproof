# PR #8 Windows review — partial, not merge approval

被审提交：`af21695c58f8286bc1467405ccf2bb2967e0ea4f`。独立 worktree，原研发工作区和历史记录未改动。当前只确认源码、安装与软件测试，**尚未完成浏览器、A4 打印和实际按钮链路验收，因此不合并任何依赖 PR**。

1. **PR #6 意见：已核对。** [5060 审查](https://github.com/tingfengy2000-creator/credproof/pull/6#issuecomment-6118121439)明确通过，附 51/51 提示一致及 24/24 Linux 复检说明。本轮不重跑模型批次。
2. **差异范围：已核对。** 实际 17 文件，不只是 4 个 UI 文件和截图。额外 6 个文件来自 `14af5cc`；逐字节等同 PR #1 的 `7bcb65e`，详见 [源数据核对](static-review.json)。PR #1 的 dev36 版本变更未带入，当前为 dev37。未额外更改执行器、规则或实验。PR #1 合并后这些相同改动应被保留一次，不撤回修复。
3. **Windows 维护测试：通过。** Python 3.12.14 / pytest 8.4.2 / qwen-agent 0.0.34；最终 255 passed / 0 skipped / 0 failed。包含全部当前维护目录、qwen_agent 依赖模块和 WindowsPath/平台测试。警告仅为 dashscope 既有弃用提示。[stdout](complete-pytest.txt)、[JUnit](complete-pytest.xml)。这不是 255 个安全任务或新模型成功。
4. **只读安装 HTTP：通过。** 本次 wheel 0.3.0.dev37，独立 venv，6 项实际 GET/拒绝 HTTP 测试通过，执行/模型接口由测试拦截；不代表页面已点击验证。[结果](readonly-http-tests.json)、[输出](readonly-http-tests.txt)。首次误用旧 dev35 安装启动会不认识 bench_results，换成由本 PR 构建的 wheel 后正常启动；未改原安装。
5. **Node：通过。** `node --check agent_pilot/ui/app.js`；`node agent_pilot/tests/test_ui_project_verdict.js` 输出 `ui-project-verdict-regression: PASS (FAIL/PASS/stale/missing cases)`。
6. **b07 源记录：通过，仅数据核对。** 指定对象 FAIL，源码摘要与漏洞原版相同，保存的 diff 为空；已核对 8 目标/88 总记录（含 21 历史）。这不代替路由实测。[原始数据核对](static-review.json)。
7. **浏览器和动态操作：阻断/未执行。** 本地地址访问先被拒绝；用户随后文字确认允许，工具仍返回 saved user permission setting blocks this action。未换浏览器、换端口或用 CDP/其它浏览器驱动绕过。因此概览、字体、矩阵、各路由 JS 日志、无 POST、A4 打印、recheck/live 实际按钮与 409 提示仍待许可解除后核验。没有新模型推理、实际业务审批或采纳。

## 实际命令和范围

```powershell
# 在本 PR 独立 worktree，使用已有完整 qwen_agent 环境；路径是本台执行收据，不是通用安装承诺。
$env:TEMP='E:/比赛/CPUI8/tmp'; $env:TMP=$env:TEMP
$env:CREDPROOF_RUNTIME_TEMP=$env:TEMP
$env:CREDPROOF_GITLEAKS='E:/比赛/密证_CredProof-local-agent/.tools/gitleaks-8.28.0/gitleaks.exe'
& 'E:/比赛/CP35/venv/Scripts/python.exe' -m pytest agent_pilot/tests credproof_safety/tests tests agent_pilot/test_model_client.py -q -rs --junitxml=E:/比赛/CPUI8/complete-pytest.xml
# exit 0, 255 passed
& 'E:/比赛/CPUI8/venv/Scripts/python.exe' -I docs/handoff/frontend-5060/test-readonly.py --output E:/比赛/CPUI8/readonly-http-tests.json
# exit 0, 6 tests OK
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
# exit 0 each
```

最初裸 `python -m pytest -q` exit 2 / 51 collection errors：它误收集历史多份 test_business.py 和 Linux-only isolation-tests/resource；[失败 stdout](full-pytest.txt)和[JUnit](full-pytest.xml)保留。随后用完整维护目录明确限定收集，不把归档漏洞样例当宿主测试；首次维护运行 240 passed/15 skipped，设置已存在固定 Gitleaks 路径后，15 项单独通过，再完整运行一次得 255 passed。不是删除失败测试缩小分母。

## 需要 5060 更新的文档

`agent_pilot/ui/README.md` 的“启动本机后端”仍称新任务经 `agent_pilot.offline_run` 启动，而实际 `web.launch_command` 使用安装解释器 `-I -m credproof_safety.web_repair` → 新边界。请在原 PR 分支更正文档，并清楚列 view/recheck/live；不恢复旧入口。

本次[安装来源收据](installed-origin.json)对应由 PR #8 源码构建的 dev37 wheel（339898 bytes），`python -I` 加载本次独立 venv 的 site-packages。没有用旧 dev35 包证明新界面可用。

主次分层、印章和打印尚未亲眼核验，不能依据旧截图或 CSS 宣称通过。所有正式人工对象仍保持 PENDING/NOT_APPLIED。用户在本轮明确选择“先发布审查记录，暂不合并”。当前结论：**测试已完成，界面复核未完成，暂不合并**。

## 公开字节与原件

[脱敏派生记录](derivation.json)中的 `public_sha256/public_bytes` 是提交 Git 前本地派生文件的摘要和长度；部分文本入库时仅 CRLF 转为 LF。[发布字节映射](publication-bytes.json)另外列出每份 Git blob 的 SHA-256、长度和精确换行关系。旧收据和本地原始日志保留，不将两种字节混用。匿名取件将按 Git blob 校验。
