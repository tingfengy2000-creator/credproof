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

合并后 Windows 官方嵌入式 Python 运行包与实际启动的收据将追加于本目录，区别程序源码提交、包摘要和后补证据提交；不修改旧包、不创建 Release。
