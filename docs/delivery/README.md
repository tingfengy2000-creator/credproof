# 默认演示与评委交付修正（dev38）

本 PR 基于 `feat/frontend-human-review-5060` 的 `c394fc2d5b7e7360065a512958fdef1963d1873e`。首轮程序为 `81426186841919d7c7750ee1cdc2e20b608a1988`；合并前两项小修后的程序/新交付包源码为 **`1796690644d9e9e2169340a2b85764a5197691bc`**，后续提交只补证据及索引。没有启动模型、执行新候选、改 bench-v1 冻结契约、CI、Docker 或报告正文。

用户确认的交付约定见 [CONTRACT.md](CONTRACT.md)，评委使用说明为 [VIEWER.md](VIEWER.md)。下列状态是本机研发验证，不是外部验收。

## PR #9 合并前小修

默认 cmd **直接启动随包 Python，不经过 PowerShell，也没有 ExecutionPolicy Bypass**；仅运行时缺失才调用 `launch.ps1` 查找系统解释器。演示副本写入 owner 标记，下次启动只清理确认原进程已退出的本程序临时目录；活跃、未知、无标记和链接目录保留。增加 Windows Ctrl+Break 的正常清理，不承诺强制结束时立即清理。

本次 **70 项定向测试通过**；真实中文加空格目录中，cmd 直接子进程为 Python 和 Windows conhost，无 PowerShell。模拟遗留目录被清理，超过 12 小时的活跃实例保留；浏览器检查 exit 0，人工审阅显示 PASS / PENDING / NOT_APPLIED，冻结 28 文件（27 件材料及清单）字节不变。新 wheel 的真实 HTTP h03 导出 200、42 项清单匹配。命令、JUnit、扫描、安装来源与截图见 [合并前证据](evidence/dev38/pr9-followup/README.md)。严格无预装 Python 的 Windows Sandbox 未执行（功能未启用）；不把本次现有账户的独立目录检查说成新用户或纯净虚拟机。

| 项目 | 处理及实际结果 | 证据 |
|---|---|---|
| P0-1 默认人工审阅为空 | `--demo` 校验 dev35 清单，再复制到随机系统临时目录。默认显示历史 v000 AI FAIL → v001 开发者 PASS，当前 PASS / PENDING / NOT_APPLIED；旧审批功能测试记录保留。实际改动/决定/静态导出只写临时副本。 | [测试](../../agent_pilot/tests/test_demo_review.py)、[新用户记录](evidence/dev38/new-user-view/new-user.json)、[截图](evidence/dev38/new-user-view/desktop-human_review.png)、[冻结 27 文件核验](evidence/dev38/new-user-view/scope.json) |
| P0-2 wheel 缺配置 | 将不含本机配置的 runtime.example.json 打入 package-data，导出与对象绑定读取同一资源；旧独立 bundle 的 config 布局仍兼容。干净 wheel 安装后实际 HTTP h03 导出 200，42 文件清单逐项匹配。 | [安装 HTTP 收据](evidence/dev38/clean-wheel-r4-http.json)、[最终安装摘要](evidence/dev38/installation-r4.json)、[复现脚本](../../scripts/delivery/check-installed.py) |
| P0-3 零安装查看 | 官方 Windows embeddable Python 3.12.10；随包 → py -3.12 → 经检查 ≥3.11 的非商店占位 Python。自动浏览器/实际地址、占用端口切换、失败留窗、正常退出清理。新标准用户、中文加空格路径、无仓库 venv/Python PATH、`-S`/isolated 运行通过；check-console exit 0。 | [浏览器完整结果](evidence/dev38/new-user-view/summary.json)、[范围与严格剩余项](evidence/dev38/new-user-view/scope.json)、[打包收据](evidence/dev38/viewer-receipt-r4.json)、[261 文件扫描及完整摘要](evidence/dev38/delivery-scan-r4.json) |
| P1-4 环境来源 | 当前硬件/Windows/WSL/bwrap/Ollama 清单及两个 Q4_K_M 模型全文件重算摘要；不是追溯声称在 bench 运行当时测量。 | [environment.json](../bench/environment.json) |
| P1-5 关闭完成 issue | #2、#5 已评论既有结果链接并关闭；没有为关 issue 重跑模型。 | [关闭收据](evidence/dev38/issue-close.json) |

上表测试/复现脚本的仓库相对路径分别为 `agent_pilot/tests/test_demo_review.py` 和 `scripts/delivery/check-installed.py`。

## 验证命令与范围

1. Python 3.12.14 / pytest 8.4.2，8 个受影响测试模块 **65 passed，0 skipped，0 warning**：完整命令、退出码、每个用例见 [command](evidence/dev38/targeted-r3-command.json)、[stdout](evidence/dev38/targeted-r3-pytest.txt)、[JUnit](evidence/dev38/targeted-r3-junit.xml)。执行于 e69c0c7；最终 8142618 只加选择框宽度 CSS 和契约目录说明，程序 Python 字节未变。`node --check agent_pilot/ui/app.js` 及现有 `test_ui_project_verdict.js` exit 0；最终 CSS 由下项真实浏览器覆盖。
2. 新用户实际启动 `cmd /d /c start-credproof.cmd`，未声称物理双击。测试预先独占 8765，程序成功改用空闲端口；临时用户无 Python PATH/HKCU 安装，无仓库 `.venv`；实际随包 3.12.10、`no_site=1`、`isolated=1`。使用已安装 Edge、包外 Playwright 1.56.1 运行原 `check-console.mjs`，exit 0，全部检查无 JS 错误、非 GET 请求或 HTTP 错误；67 列对齐，390px 无横向溢出，深色与打印生成正常。截图/PDF及每页事实见 [完整浏览器目录](evidence/dev38/new-user-view/)。Ctrl+C 正常退出后临时审阅目录剩余 0；临时账户已删除。
3. 最终 wheel 在独立环境重新安装，用 `python -I scripts/delivery/check-installed.py --workspace <固定材料目录> --output <结果.json>` 执行真实本地 HTTP 导出。程序来自 site-packages，模块摘要与 wheel、源码工作树匹配；Git LF 与工作树/wheel CRLF 摘要分别登记，未混用。
4. 为删除交付源码的作者固定路径，旧 sandbox_runner 默认改用当前用户目录，并将作者/盘符特定的自探针改为检查空 home/mount。没有改变项目判决规则。因 runner 字节改变，实际执行一次 `agent_pilot.isolation prepare`、`probe`（均 exit 0），[结果](evidence/dev38/legacy-boundary-probe.json)和[范围](evidence/dev38/legacy-boundary-command.json)单列；只是可信无害边界自检，没有候选执行、模型或真实凭据。

## 剩余验收条件与保留失败

**严格的“宿主完全没有预装 Python”条件未完成。** 新用户环境无 Python PATH/HKCU 安装，且程序实际使用随包隔离运行时；但宿主存在系统级 Python 注册，不能冒称纯无 Python 虚拟机。可用 Windows Sandbox 未启用，本轮不改系统功能或卸载其他 Python。默认浏览器调用已请求且没有报告失败；自动页面验证使用另一独立 headless Edge，不把它当成肉眼确认了新用户交互桌面的浏览器窗口。需要最终纯无 Python 环境的启动体验复验。

开始的 `_pth` 根路径错误、Windows 独占端口 10013、测试脚本 cwd/TEMP 问题及长审阅名称的 390px 溢出均保留在 [attempts](evidence/dev38/attempts/index.json)。原始私有记录本地保存；公开件只对确实的本机路径脱敏并记录前后摘要，没有改旧测试结果。没有用本轮查看启动检查替代 recheck/live 动态安全验收；已有适用的历史动态证据保持原日期和范围。

## 白名单、脱敏与交付文件

构建命令：`python scripts/delivery/build.py --python-zip <官方原始ZIP> --output <新的输出目录>`。官方 ZIP 来源和固定 SHA-256 见收据；Python 许可保留。源码、历史和运行时按显式白名单复制，不含 `.git`、`docs/handoff/**`、`docs/review/**`、模型/rootfs/venv 或内部审查材料。

`scan.py` 扫描整棵交付树及可读 ZIP 内件，**261 文件、敏感命中 0**。官方许可中的公开法律联系邮箱和受控模型命名空间 `/home/model` 是精确位置/字面值白名单，单列 `reviewed_non_host_literals`；没有删许可、宽泛忽略文件或声称检测所有秘密。二进制内部不当成源码解码。机器代称不出现在交付 HTML/JS/CSS 的页面文案；内部 UI README 不入包。

小修后的本地文件 `credproof-viewer-0.3.0-dev38-r5.zip`：**11,642,060 bytes**，SHA-256 **`feb0b1ba0b11ede1825c772fca43531ab2ee75e2227fd71b337ee8fef15d9107`**，源码为上述 1796690。旧 r4 包（11,640,265 bytes，SHA-256 `75ba9d6997eaccb37ad04bd3906d0a88beb77c41c24eda0877a9c9a8b7260f4c`）保留。不将 ZIP/解释器/第三方二进制提交 Git，不创建 Release；GitHub 提供构建脚本、固定来源与完整收据，自动源码 ZIP 不等于该运行包。
