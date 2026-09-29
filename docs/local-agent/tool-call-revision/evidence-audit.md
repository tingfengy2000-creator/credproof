# 工具调用修订前：新 8 例事实审计

本次只读复核 **20260929t095000z-holdout8** 的原始 30 行记录、逐方法结果、候选源码、模型消息和请求回执；未执行候选或模型，未修改历史结果。审计工作区起点为 `65abca2ac6c531f2b790cf893da7a0c5ad166752`，它不是“整次执行使用的版本”声明；实际执行以该轮 `frozen-inputs.json` 为准。语义判断是 **Codex 自审，不是独立人类评审**。旧 6 例成绩不并入本表；此后 p01–p06、h01–h08 共 14 例统一称为**已知回归案例**，不能再次作为未见留出集。

原始入口：[results.json](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/results.json)、[冻结记录](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/frozen-inputs.json)、[supervisor](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/supervisor-result.json)。本轮监督命令退出码 0，`frozen_inputs_unchanged=true`。本次另核对 30 行与各自 `result.json` 一致，原始/最终源码哈希和最终选中对象一致。机器表：[prior-case-audit.json](../../../experiments/local-agent-pilot/tool-call-revision/prior-case-audit.json)。

## 三层结果必须分开

“任务完成”沿用执行器记录；“最终对象 PASS”是独立最终验收，可能验的是未修改原文件；“诊断”指有效结构化 `initially_leaking`，不代表模型独立发现，也不代表根因解释全部正确。A/B/C 都先收到相同固定触发的实际初始证据：有漏 4/4 被程序确认，正常误确认 0/4。

| 方法 | 任务完成 | 有漏案例修复合格 | 最终对象 PASS | 有漏结构化判阳性 | 正常结构化正确 / 错误 / 缺失 |
|---|---:|---:|---:|---:|---|
| A 固定规则 | 7/8 | 3/4 | 7/8 | 4/4 | 3/4、1/4、0/4 |
| B 一次生成 | 4/8 | 1/4 | 5/8 | 4/4 | 3/4、0/4、1/4 |
| C Agent | 6/8 | 4/4 | 8/8 | 4/4 | 2/4、0/4、2/4 |

本表确切计数布尔式为 `task_complete = task.task_status in {COMPLETED_REPAIRED, COMPLETED_UNCHANGED}`；不读取 `model.status` 替代它，也不由最终 PASS 反推任务完成。本次额外逐行核查：每个计入完成的记录，其最终验收均 PASS，且存在对当前 `selected`、当前 `candidate_sha256` 与 `rules_sha256` 完全匹配的 PASS 验证回执；其余记录保持未完成。该机械任务判据**不要求诊断正确**，所以 A 的 h05 可同时“任务完成”和“诊断误报”。

模型结束与任务结束的原始字段如下（R=`COMPLETED_REPAIRED`，U=`COMPLETED_UNCHANGED`，I=`INCOMPLETE`；本表的状态均来自各例记录，不来自总摘要）：

| 案例 | B `model.status` / `task_status` | C `model.status` / `task_status` |
|---|---|---|
| h01 | COMPLETED / I | EXECUTOR_COMPLETED / R |
| h02 | COMPLETED / R | EXECUTOR_COMPLETED / R |
| h03 | COMPLETED / I | EXECUTOR_COMPLETED / R |
| h04 | COMPLETED / I | EXECUTOR_COMPLETED / R |
| h05 | COMPLETED / U | COMPLETED / I |
| h06 | COMPLETED / U | COMPLETED / I |
| h07 | COMPLETED / I | EXECUTOR_COMPLETED / U |
| h08 | COMPLETED / U | EXECUTOR_COMPLETED / U |

A 没有模型状态，其任务逐例为 h01=I、h02/h03/h04=R、h05/h06/h07/h08=U。D 的 h01 seeds 1/2/3、h03 seeds 1/2/3 六条均为 `model.status=COMPLETED`、`task_status=INCOMPLETE`。因此“生成正常结束”本身既不保证诊断格式有效，也不保证补丁合格或任务验收完成。

A 的唯一失败是 **h01，不是 h03**。下面每格“任务 / 最终对象”均链接其原始记录；“未完 / PASS”不能改写成成功。

| 案例 | A | B | C | 主要事实 |
|---|---|---|---|---|
| h01 有漏 | [未完 / FAIL](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/A-fixed/result.json) | [未完 / FAIL](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/result.json) | A 只处理返回内容，帮助函数仍记录传入凭据；B 源码仅空白变化，AST 不变。 |
| h02 有漏 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/A-fixed/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/C-agent/result.json) | 三者均消除输出泄露并通过功能检查。 |
| h03 有漏 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/A-fixed/result.json) | [未完 / FAIL](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json) | A 首候选已通过；C 第二候选通过；B 仅末尾换行变化。 |
| h04 有漏 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/A-fixed/result.json) | [未完 / FAIL](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/C-agent/result.json) | B 虽判有漏却返回原代码，无候选，泄露仍在。 |
| h05 正常 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/A-fixed/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/B-once/result.json) | [未完 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/C-agent/result.json) | A 误判并提案，被无泄露证据门槛拒绝；C 仅伪工具文本。 |
| h06 正常 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/A-fixed/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/B-once/result.json) | [未完 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/C-agent/result.json) | C 同样只有普通文本，无原生工具调用。 |
| h07 正常 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/A-fixed/result.json) | [未完 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/C-agent/result.json) | B 原文判断正常，但 JSON 转义错误，结构化诊断缺失；C 验原对象。 |
| h08 正常 | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/A-fixed/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/B-once/result.json) | [完成 / PASS](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/C-agent/result.json) | B/C 有潜在信息暴露猜测，未明确断言实际凭据泄露；C 三次无效对象测试被拒后验原对象。 |

正常源码实际不必要修改均为 **A/B/C 各 0/4**，不等于没有误报：A 的 h05 是固定程序误报 1/4，不能记作 LLM 误报。B 正常原文没有肯定实际泄露的断言；h08 有疑点描述，h07 机器字段仍缺失。C 正常原文没有肯定实际泄露的断言，但 h05/h06 **没有可评分诊断**；不能表述成“正常判断正确 4/4”或隐去缺失后仅报零误报。B 的 h05/h06/h08 三份被拒源码提案仅缺末尾换行，AST 相同，不是三次实质错误修复。

h05/h06 的 C `model-01-response.json` 只有 `message.content` 中的 `<function=read_code>…`，没有 `tool_calls`；`tool_trace=[]`、诊断为空、无候选/验证。`model.status=COMPLETED` 仅表示生成结束，未发生真实 `read_code`。[h05 原始响应](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/C-agent/model/model-01-response.json)、[h06 原始响应](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/C-agent/model/model-01-response.json)。

## h03：真实迭代成立，根因解释不完全正确

[C 轨迹](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json) 的零基索引：`tool_trace[3]` 提交候选 1，`[4]` 验证 FAIL（logging 泄露，11 PASS / 2 FAIL）；该失败通过原生调用 `call_cpjy5xro` 进入[下一请求](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/model/model-06-request.json)的 `messages[11]`。随后 `[5]` 提交候选 2、`[6]` 验证 PASS（13/13），最终源码哈希对应候选 2。

[候选 1](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-1.py) 把前缀 `credential=` 替换为 `credential=[REDACTED]`，**未移除前缀后真实值**。模型 `model.messages[13]` 却把失败解释为日志仍出现字面词 `credential=`，这个解释错误。[候选 2](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-2.py) 用固定错误详情替换动态异常字符串，消除了值，固定文本依然含 `credential` 单词也能通过。因此本轮支持“收到失败反馈后产出合格候选”**1 次 / 1 次实际失败候选机会**，不支持“精确理解首补丁失败根因”或稳定迭代成功率结论。此前同对象同条件的受控调用返回缓存初始证据，不应计为新增独立复现实验。A 的 h03 首补丁已通过，不能把该例写成 C 优于 A。

## D 预算与解释边界

D 只覆盖 h01/h03，每例 seeds 1、2、3 各一次无反馈生成，六份结果全部保留；不是六个独立案例，也没有选优。六份候选均与原文件 AST 相同、只有空白差异，全部 FAIL（logging `CREDENTIAL_LEAK`），所以是 **0/6 次修复合格**。逐条路径、失败原因、seed 和 tokens 均在机器表。

记录的最大输出额度：C 每例 `12×2048=24576`，D 每例三份合计 `3×8192=24576`；这只是上限相同，不是实际 tokens、输入上下文或计算量匹配。仅比较双方共有的 h01/h03：

| 方法与范围 | 实际模型调用 | 输入 tokens | 输出 tokens |
|---|---:|---:|---:|
| C，h01+h03 | 11 | 39,265 | 2,968 |
| D，h01+h03 共六份 | 6 | 9,567 | 3,428 |

所有 8 例 C 合计 31 调用、99,142 输入 / 6,648 输出；B 合计 8 调用、12,567 输入 / 4,634 输出。不能据此宣称等计算预算优势。执行器已共享初始诊断证据，当前结果主要反映受限 Python 案例上的修复、工具使用和验收完成情况，不证明自主发现现实漏洞的普遍能力。后续工具调用修订应独立记录新轮结果，保留本轮 h05/h06 不完整任务和 B 的格式失败。
