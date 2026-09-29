# 已知 h05/h06：一次真实复测审计

本报告只审计 `20260929t114543z-known-h05-h06`，源码提交为 `6fadc5db6bd02c9bd3012b76417ca498eb413006`。这是两个**已知正常回归案例**的真实本地模型运行，不是 HTTP 重放或新留出测试。Codex 只读核对记录，未运行模型、候选或修改历史成绩；原文语义分类为 Codex 自审，不是独立人类评审。另六例的后续复跑不并入本报告。

**结论：本轮两例均完成原对象验收，但格式纠正分支均未触发。** 新旧首请求 JSON 内容逐例完全相同；旧首响应是普通正文伪工具文本，新首响应已经有原生 `tool_calls`。因此不能将成功归因为“纠正提示救回”，也不能把旧轮 C 的 6/8 任务完成改成历史 8/8。

入口：[新轮结果](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/results.json)、[旧轮结果](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/results.json)、[逐调用机器表](../../../experiments/local-agent-pilot/tool-call-revision/retest-results.json)。

## 逐例对照与实际调用

| 指标 | 旧 h05 | 新 h05 | 旧 h06 | 新 h06 |
|---|---|---|---|---|
| `model.status` | COMPLETED | EXECUTOR_COMPLETED | COMPLETED | EXECUTOR_COMPLETED |
| `task_status` | INCOMPLETE | COMPLETED_UNCHANGED | INCOMPLETE | COMPLETED_UNCHANGED |
| 结构化 `initially_leaking` | 缺失 | false | 缺失 | false |
| 独立最终对象 | PASS 13/13 | PASS 13/13 | PASS 13/13 | PASS 13/13 |
| 模型调用 | 1 | 6 | 1 | 8 |
| 输入 / 输出 tokens | 1,975 / 20 | 20,274 / 729 | 1,972 / 20 | 29,741 / 1,166 |
| 方法总耗时（秒） | 2.682 | 8.850 | 2.577 | 11.489 |
| 模型会话耗时（秒） | 0.303 | 6.569 | 0.268 | 9.122 |
| 纠正安排次数 / 实际首调用 ID | 不启用 | 0 / `[]` | 不启用 | 0 / `[]` |
| 原生工具派发 | 0 | 6 | 0 | 8 |
| 补丁提案 / 被拒 / 候选写入 | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 0 |

模型会话时间包含会话中的工具等待，不能等同 GPU 纯生成时间。新轮合计 14 次调用、50,015 输入 / 1,895 输出 tokens；方法耗时合计 20.339 秒。相较旧两例，新增的 5、7 次请求都是原生工具循环的后续请求，**不是纠正提示产生的额外请求**。纠正首请求数为 0，纠正后循环请求数也为 0。会话仍使用总上限 12 次、每次最大输出 2,048、16,384 上下文、seed 0，无自动重试；两例均无 ERROR/timeout。

### h05

[新首响应](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h05/C-agent/model/model-01-response.json) 的 `call_szz8d5g8` 为真实 `read_code`；[旧首响应](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/C-agent/model/model-01-response.json) 则只有正文 `<function=read_code>…`。

[逐工具轨迹](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h05/C-agent/result.json) 零基索引：`[0]` 读取；`[1]` 使用不存在的 `candidate_id=test-1`，被拒；`[2]–[4]` 对成功、无效输入、拒绝授权执行三个新增实际条件，均 PASS；`[5]` 原生 `verify_patch(original, initially_leaking=false)`，13 项均 PASS。最后验证调用 ID 为 `call_x1s40kbj`。没有补丁提案，原文件未改。

模型第 2 次响应已经表示 “No credential appears in return values, logging output, or any other channel.”，其后是进一步确认，无肯定实际泄露的误报。所有前序真实工具回执都进入下一请求；不存在把伪调用正文补算成执行的情况。

### h06

[新首响应](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h06/C-agent/model/model-01-response.json) 通过 `call_senmh86i` 原生读取。[逐工具轨迹](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h06/C-agent/result.json)：`[1]` 无效对象测试被拒，`[2]–[4]` 三个新增实际条件均 PASS，`[5]` 再读安全证据，`[6]` 仍提出删除 `_public_provider_error` 中公开 `request_id` 日志的补丁。

第 7 次响应原文有 “I have identified a potential leak”，同时又明确 “there are no signs of the credential leaking directly”。它属于**无证据支持的潜在风险疑点和不必要修复提案**，不是已经确认实际凭据值泄露的断言。不能因为最终 `false` 就隐藏这次错误行动建议。[原始响应及完整提案](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h06/C-agent/model/model-07-response.json)。

系统以 `no_current_confirmed_leak_evidence` 拒绝 `call_r3namdx7`，未写入候选。该拒绝实际进入[第 8 次请求](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/h06/C-agent/model/model-08-request.json) 的 `messages[15]`。随后模型承认缺少确认依据，以 `call_35vncsl9` 验证原对象，并明确日志只含公开 request_id；13 项 PASS 后执行器终止。这支持“拒绝提案反馈后转为保留并验证原文件”1 次，不是“失败补丁迭代修好”——本轮没有落地候选，也没有失败候选后修复机会。

## 分层指标和对象核验

仅这两个正常案例：任务完成 2/2、最终对象 PASS 2/2、最终结构化正常诊断 2/2。原文肯定实际凭据泄露的断言为 0/2；但潜在风险疑点并产生不必要提案为 **1/2（h06）**。系统错误确认泄露 0/2，不必要提案被拒 1/1，实际不必要修改 0/2。不能只用“零误报”概括整个过程。

逐例核对：`selected=original`、`candidate_count=0`，目录没有 `candidate-*.py`；原始和最终文件逐字节相同，均与旧同例原始文件一致。当前对象哈希、规则哈希和 PASS 验证回执匹配，最终独立复检仍 PASS。`task_status` 两例均为 `COMPLETED_UNCHANGED`，并非由最终 PASS 单独推导。公开记录中未发现合成运行凭据的完整 `CP_EXEC_` 加 48 位十六进制值；本次审计未读取 private 日志。

## 冻结、离线环境和显存

[监督记录](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/supervisor-result.json) 显示握手和两例命令均退出 0；两例命令耗时 25.115 秒，包括独立原始预检等方法外开销。[冻结记录](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/comparison/frozen-inputs.json) 含 35 个文件，结果 `frozen_inputs_unchanged=true`；审计时重新计算也均匹配。

[运行前网络](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/network-before.json)、[运行后网络](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/network-after.json) 均只有 `lo`，无可用外部路由；每次对三个记录地址的连接测试均失败。[命名空间记录](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/namespace-membership.json) 显示编排器与 Ollama 同属 `net:[4026532230]`。这支持该子进程命名空间的离线执行边界，不是对整台宿主所有应用的网络声明。

[显存采样](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/resources.json) 共 19 条，按 `memory.used,memory.free,utilization.gpu` 采样，已用峰值 **19,168 MiB（18.719 GiB）**，最低空闲 13,020 MiB，采样利用率最高 78%；这是采样最大值，不是连续监控的严格峰值。[模型驻留记录](../../../experiments/local-agent-pilot/tool-call-revision/20260929t114543z-known-h05-h06/model-ps.json) 为本地 `qwen3-coder:30b`、Q4_K_M、16K 上下文。此次两例没有发生原格式故障，所以纠正路径的控制流证据仍来自标明 REPLAY 的测试；本轮实测只证明这两次新轨迹成功完成。
