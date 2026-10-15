# PR #22：Windows 只读页面与交付核对

被测实现：`3686c289ce73a36f854ed92cf37852240cfb31b1`；原 PR 头：`8e3ebb7e5f6698cd76f5da1b36d05b0aade9a57c`；目标主线：`feat/frontend-human-review-5060`。仅页面、只读数据与打包范围验证，新增模型调用、候选执行、安全实验均为 **0**。

## 审查和修正

- `agent_pilot/web.py:Application.compare` 只读取工作区内两个固定 JSON，4 MiB 上限并核对 schema；GET 路由不接受文件路径，不执行项目。沿用 Host/Origin 边界。
- 原头提交的严格只读入口虽然放行 `/api/compare`，临时根未包含对应 JSON。新增正式回归在原实现上实际得到 `404 != 200`（退出 1）；修正 `prepared_view`，将固定的两份材料复制到临时副本，拒绝链接及超限文件。原件不写入，POST 仍为 405。
- `build.py:inventory` 只新增两份明确文件，不扩大到整个 docs 或任何环境目录。
- 页面将 FAIL 分组准确标为“未满足声明条件”：它包括安全违规、业务破坏和过度拒绝。无效回答独立列出，是所有覆盖对象上的交叉计数，不能当作全部发生在合格对象上；冻结 JSON、分母和结果均未改变。

## 实际检查

Windows，Python 3.12.14 / pytest 8.4.2，Microsoft Edge 155.0.4283.45。以下路径占位符对应操作员目录，原记录留本地；逐件原始/公开摘要见 [provenance.json](provenance.json)。

|检查|实际结果|证据|
|---|---|---|
|受影响的软件、HTTP/只读协议、已有展示/提议入口回归|50 passed，退出 0；1 个 DashScope SDK 弃用 warning，无 API 调用|[命令与退出码](software/software-checks.json)、[stdout](software/pytest.stdout.txt)、[JUnit](software/pytest.xml)|
|冻结 JSON 复算、JS 语法、判决显示回归|均退出 0|同上命令收据|
|`--demo --mode view` 全部路由浏览器检查|PASS，退出 0；无 JS 错误、HTTP 错误或非 GET 请求|[summary](console-view/summary.json)、[A4 PDF](console-view/report.pdf)|
|严格只读入口全部路由浏览器检查|PASS，退出 0；无 JS 错误、HTTP 错误或非 GET 请求|[summary](console-readonly/summary.json)、[A4 PDF](console-readonly/report.pdf)|
|`#compare` 四批次、各方法分母/无效数、dotenv 四版本计数、390px 布局|PASS，退出 0，零写请求|[逐项正文](compare-view/summary.json)、[桌面截图](compare-view/compare-desktop.png)、[窄屏截图](compare-view/compare-mobile.png)|

启动和浏览器命令（仓库根执行；严格只读使用 `-m`，避免直接脚本配合 `-S` 时源码根不在搜索路径）：

```text
<test-python> -S -m agent_pilot.launch --workspace <disposable-workspace> --demo --mode view --port 0
<test-python> -S -m docs.handoff.frontend-5060.view-readonly --bench-results docs/bench/bench-results.json --port 0
node <review-worktree>/docs/ui/console-v1/check-console.mjs --base <printed-local-address> --out <new-output-directory>
node <review-worktree>/docs/review/evidence/pr22-windows/check-compare.mjs <printed-local-address> <new-output-directory>
```

浏览器命令从已安装 Playwright 1.56.1 的目录执行，使用现有 Windows Edge；不下载浏览器。不宣称这些软件/只读检查是新的模型修复或安全集成实验。旧 Agent 失败、人工修复来源及历史统计保持原样。

## 合并后的 Windows 运行包

PR #22 已合并，包内源码提交为 **`30acb104e02e5a6227386c8df9e21ffb77f10c28`**。合并树与已审查 PR 头树完全相同；相对被测实现 `3686c28`，程序、测试、只读入口和两份数据的差异为空，只有审查证据新增。随后交付提交仅添加收据，不改变这个包。

- [cp22-30acb10.zip](https://github.com/user-attachments/files/33466388/cp22-30acb10.zip)，**11,753,546 bytes**。
- SHA-256：`66529367073b0e207685ab77591e905066e79cf75e3f9d8c0f0ecd7cdfe1dd28`。
- [构建收据](package/receipt.json)、[完整包内文件摘要](package/file-manifest.json)、[脱敏扫描](package/scan.json)：310 个文件检查，敏感命中 **0**。
- [实际启动/来源与必需文件核对](package/verification.json)：Windows 中文＋空格目录，直接运行 `start-credproof.cmd --port 0`；来源是随包 Python 3.12.10，`-S` 下仅包内标准库/源码路径，不使用仓库 `.venv`、WSL、模型或作者 PYTHONPATH。两份 JSON 与固定 Git blob **逐字节相同**，8 个 bench 示例配置仍存在。
- [包内全部路由检查](console-package/summary.json)：`check-console.mjs` exit 0，PASS；无 JS/HTTP 错误和非 GET 请求；[A4 PDF](console-package/report.pdf)。[包内对照页逐批检查](compare-package/summary.json) exit 0，四批次、dotenv 四版本、390px 均通过；[截图](compare-package/compare-desktop.png)。
- [匿名取件收据](package/anonymous-fetch.json)：8 个固定源码/证据 Raw 正文与 Git blob 比较一致；附件实际重新下载的长度、SHA-256、ZIP CRC 和两份 JSON 均通过。请求不带 Authorization/Cookie。附件不是 GitHub 自动源码 ZIP。

此处复用现有 Windows 主机并用随包解释器实测，不称为新建 Windows 用户或另一台机器验收。没有新的候选执行、安全实验或模型推理。旧包不覆盖，main 不改动，不创建 Release。
