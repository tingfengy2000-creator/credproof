# PR #9 合并前定向验证

程序、wheel、查看包来源：`1796690644d9e9e2169340a2b85764a5197691bc`。本目录为随后添加的证据，不声称证据提交本身参与运行。仅默认启动和临时副本管理改变，没有模型调用、候选执行、WSL、安全场景、CI 或 Docker 运行。

| 验证 | 结果与原始依据 |
|---|---|
| 8 个受影响 pytest 模块 | Python 3.12.14 / pytest 8.4.2；70 passed、0 skipped、0 warnings；[stdout](targeted-pytest.txt)、[JUnit](targeted-junit.xml)、[命令](commands.json) |
| 默认 cmd 实际启动 | 官方 embedded Python 3.12.10，`-S`、isolated；新解压目录包含中文及空格；8765 独占后自动选端口。直接子进程只有 python.exe 与 Windows conhost.exe，无 PowerShell；[启动/清理收据](cmd-view/result.json)、[stdout](cmd-view/startup.txt) |
| 启动时遗留清理 | 同一受控 TEMP 内放入已退出子进程 marker、活跃 PID marker（13 小时前）、无 marker 目录：只删除第一种。Ctrl+C 后本次演示副本清理；冻结 28 文件（27 件材料+清单）不变。没有终止其他实例或进程。 |
| 实际浏览器 | 已安装 Edge + Playwright 1.56.1，原 `check-console.mjs` exit 0，路由/旧锚点、只读请求、67 列对齐、390px、打印和深色检查；[summary](cmd-view/summary.json)、[人工审阅截图](cmd-view/desktop-human_review.png)、[窄屏截图](cmd-view/mobile-human_review.png)、[打印 PDF](cmd-view/report.pdf) |
| 干净 wheel 重新安装 | `python -I` 的程序来自 site-packages，相关模块与新 wheel/工作树逐字节一致，Git LF 与安装 CRLF 分别记摘要；h03 HTTP 导出 200、42 文件清单一致；[安装摘要](installation.json)、[HTTP 原始收据](clean-wheel-http.json) |
| 包与敏感扫描 | 新 r5 包 11,642,060 bytes；SHA-256 `feb0b1ba0b11ede1825c772fca43531ab2ee75e2227fd71b337ee8fef15d9107`；261 文件、敏感命中 0；[包收据](viewer-receipt.json)、[逐文件摘要/扫描](delivery-scan.json) |

Windows 残留清理用 `OpenProcess(QUERY_LIMITED_INFORMATION)` 和 `GetExitCodeProcess` 只读查询，不用 Windows `os.kill(pid, 0)`。仅当前系统临时目录的直接子项、固定前缀+有效 owner、非链接且原 PID 确认已退出才删除；活跃进程即使超 12 小时也保留。权限不明时保留，PID 复用时也可能保守保留。无 marker 的历史遗留不自动删除。

## 尝试与范围

新增测试首次定位 owner 时误用了 `runs/owner.json`，得到 1 failed/69 passed；修正测试为实际 TemporaryDirectory 根后 70 passed，程序未因此变化。[原失败](attempts/initial-test-pytest.txt)、[原 JUnit](attempts/initial-test-junit.xml)。第一次启动脚本在开始 CMD 前遭 `SystemRoot` 大小写 KeyError；第二次实际启动与浏览器均正常，但过严的测试断言把 Windows conhost.exe 视为异常，[原收据](attempts/cmd-conhost-assertion.json)、[当次浏览器结果](attempts/cmd-conhost-browser-summary.json)。修正测试断言后使用新目录重测成功。没有改写旧结果。

一次新用户测试脚本组合命令被工具策略拒绝，未执行；本次改用现有账户、独立解压目录及受控测试 TEMP，无新账户创建或系统策略修改。首轮新标准用户结果仍见上一层目录，不能把它的范围改成此次新测试。

严格“宿主完全无预装 Python”的 Sandbox 仍**未执行**：`Containers-DisposableClientVM=Disabled`。不启用系统功能、不重启、不卸载 Python。默认浏览器调用已发起；自动页面核验用 headless Edge，不冒称肉眼确认了自动打开窗口。Ctrl+Break 已注册正常处理分支，本轮实际退出发送的是 Ctrl+C；强制关闭仍以次次启动回收为准。

原始记录留在本地，公开件只映射明确本机前缀、删除 JUnit hostname；[来源与原始/派生摘要](provenance.json)。状态、失败和数字不改写。原 r4 包及所有历史记录保留；本轮不重复旧动态安全/模型实验。
