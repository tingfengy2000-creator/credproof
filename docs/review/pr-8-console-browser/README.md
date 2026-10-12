# PR #8：Windows 浏览器、打印与实际按钮补验

被审源码：`79e6b74627b4001ac071bd831d4133c1ccb10c8a`（`feat/console-ui`）。本目录仅添加审查证据；没有修改 PR 的程序、UI、检查器或模型配置。前次被权限阻断的记录保持原样，本目录补充后续实际结果。**新增模型调用 0；人工决定仅为独立临时副本中的审批功能测试；原项目/index 未应用；未合并 PR。**

## 浏览器保存的拒绝：已定位并解除

用户截图中的全局设置确实允许 `http://127.0.0.1:8768`，但本聊天的 `browser/sessions/<thread-id>.toml` 同时保留了该 origin 的 denied 项。备份后只移除这一条冲突记录，原 CUA 内置浏览器随即能够访问同一个地址，并完成下述按钮操作；没有换端口或用替代驱动绕过拒绝。

这是实际观察到的全局/聊天权限不一致；没有证据进一步判定应用内部为何没有同步。完整设置和其他站点不公开。[精确修改与结果收据](permission-resolution.json)。当前保留的页面为 view 查看模式，不会点击模型启动。

## 验证结果

| 项目 | 本次结果及证据 |
|---|---|
| demo 查看入口 | 原提交的 `check-console.mjs` 在 Windows、已安装 Edge 155 / Playwright 1.56.1 实跑，exit 0，0 failures。[summary](check-demo/summary.json)、[A4 PDF](check-demo/report.pdf) |
| 严格只读入口 | `view-readonly.py --bench-results ...` 同样实跑，exit 0。各路由没有 JS 报错、HTTP 错误或非 GET 请求。[summary](check-readonly/summary.json)、[A4 PDF](check-readonly/report.pdf) |
| 路由与布局 | 新路由、旧锚点、390px 宽度及深色模式检查完成；实际矩阵 67 列 / 5 行，8 个目标。脚本检查 misaligned=0、overflow=0。[概览](check-demo/desktop-overview.png)、[移动端](check-demo/mobile-overview.png)、[深色](check-demo/desktop-overview-dark.png) |
| 指定 b07 补丁 | 显示“不通过”“与漏洞原版逐字节相同”；差异为空。额外 GET-only 断言补齐原脚本未断言的内容。[断言](supplement-recheck-loaded/summary.json)、[截图](supplement-recheck-loaded/b07-readonly.png) |
| 字体和 A4 | Microsoft YaHei、SimSun 的注册表安装项均存在；脚本的宽度启发式 SimSun=false 不是字体缺失证据。两份 PDF 共 4 页已渲染、逐页目视检查，中文、印章、续页表头清楚，无裁切或重叠。[检查说明](font-and-pdf-review.json)、[demo 第1页](check-demo/report-page-1.png)、[第2页](check-demo/report-page-2.png) |
| 人工审阅（安装版） | 保存仅添加注释的开发者修订产生 v002，旧 PASS 不沿用；页面重新验收真实执行后 PASS，必要业务用例 4/4、14 条条件均满足。测试采纳、需要修改、拒绝，以及诊断/已采纳两种 ZIP 下载成功。[完整报告](human-review-check.json)、[请求/响应](manual-events.jsonl)、[下载摘要](download-receipts.json) |
| 会话和冲突 | review 请求携带匹配的 `X-CredProof-Review-Session`；`expected` 包含 version/object/report/decision_count。第二页修改后原页提交得到真实 409 `stale_version_or_material_changed`，页面提示“请求失败，保留的记录不能当作最新状态。”刷新后拒绝成功。[逐次请求摘要](button-request-summary.json) |
| FAIL 状态 | 从既有历史 FAIL 建新审阅仍为 FAIL/PENDING/NOT_APPLIED，采纳和已采纳导出禁用；没有新推理。[状态断言](manual-state-captures/summary.json)、[截图](manual-state-captures/6f5ae3791ad343b7ba4ebdf9e52b9d8a.png) |
| h03 源码启动 | 页面“重新验收”产生新独立 PASS，“导出证据包”返回 ZIP 200。历史运行和本次复检仍独立显示。[新复检报告](h03-source-recheck.json)、[逐次响应](manual-events.jsonl) |
| h03 wheel 启动 | **有问题**：复检返回 409，在动态执行前被完整材料检查拒绝。wheel 缺少 `site-packages/config/runtime.example.json`，`agent_pilot/bundle.py:216` 读取失败。不能把源码入口成功写成安装包流程成功。[安装版只读复现](wheel-config-check.txt) |
| live 按钮 | 安装版显示“现场修复：可调用本地模型”，启动按钮启用；**未点击**，不产生模型调用。[断言](supplement-live/summary.json)、[截图](supplement-live/workbench.png)、[实际模块来源](manual-origin-live-installed.json) |

所有动态复检仅在本台 5090 的既有 WSL/bubblewrap 环境执行。审批测试和修订只作用于独立复制的数据。`PASS/REJECTED(test)/NOT_APPLIED` 的并列展示已核对：[截图](manual-state-captures/939e25f42bb142f39567c5cb644ebc6d.png)。这不是代替用户采纳，也不是模型修复成功。

## 仍需处理的具体项

1. **安装包历史 h03 导出缺配置。** 属于现有打包/导出依赖，PR #8 未修改相关核心代码；本次不擅自修受保护实现。源码启动的 replay 复检/导出已通过，但不能宣称 wheel 版这一入口完整通过。
2. 原浏览器脚本的 PASS 覆盖范围仍应收窄或补强：矩阵不存在也可能不报错；没有直接断言 b07 FAIL/相同源码/空差异；字体是宽度启发式。上述当前版本事实由本目录的额外断言和人工查看补验，**未修改 PR 的脚本**。请 5060 如需改脚本，在同一 PR 追加。
3. live 只检查提示和按钮，不进行新推理；新模型任务不在本次授权范围。前次 42 项协议回归和更早 255 项维护测试继续引用对应版本的既有证据，不声称本次重跑：[前次记录](../pr-8-console-followup/README.md)。

## 原始记录、命令和适用版本

- [命令、实际退出码和执行范围](commands-and-results.json)
- [人工操作完整脱敏 HTTP 事件/响应](manual-events.jsonl)；会话仅记存在与匹配布尔值，不记录令牌。
- [安装版 recheck 来源](manual-origin-recheck.json)、[源码版来源](manual-origin-recheck-source.json)、[安装版 live 来源](manual-origin-live-installed.json)。对应模块字节摘要一致；数据目录与程序安装分离。
- [材料映射与原始/公开摘要](derivation.json)。原件留本地，JSON 仅对已知本机路径前缀做结构化映射；不改代码、判决、对象摘要或错误原因。截图/PDF 保持原始字节。
- `helpers/` 是本次独立复制数据与只读断言的辅助脚本。程序操作仍调用原 Application/Handler，观察器仅记结果；公开路径用占位符，复用时需填写相应本地目录。它们不是新的产品启动器或安全检查器。
- 补充截图脚本第一次在异步内容加载完成前取值，exit 1 的 [原摘要](supplement-recheck/summary.json) 保留；修正等待条件后 [exit 0](supplement-recheck-loaded/summary.json)。另一次截图 helper 的标签定位不匹配导致退出 1，改用实际 `#review-saved` 后成功；均不执行候选或发 POST，不能算产品判决失败/成功样例。

本次仅完成审查和证据交付。遵循用户“先发布审查记录，暂不合并”的安排，**PR #1/#3/#4/#6/#7/#8 均未由本轮合并，main 和冻结基线未修改**。后续是否合并由用户决定；本目录不宣称第三方验收、比赛提交或完整现场模型流程已经通过。

## 后续授权与合并结果

上段是本批审查证据生成时的状态，保留其时间顺序。用户随后明确要求本轮合并，已按 `#8 → #7 → #6 → #4 → #3 → #1` 合入各自 base，逐项核对 `merged=true`。项目主线 `feat/frontend-human-review-5060` 最终为 **`c394fc2d5b7e7360065a512958fdef1963d1873e`**，最终树与合并前本地 `merge-tree` 的 `6a6f3aed61d4958d6ee99bce2d1d18ca81d12fbc` 一致。main 未变化；PR #1 的附加交接文档没有改变被测程序。没有执行冲突改码或新模型任务。[逐项合并收据](merge-receipt.json)。

安装版 h03 缺配置仍为上文记录的已有打包问题，不因合并变成已通过。正式用户采纳、赛事提交和第三方认证仍不在本次结论内。
