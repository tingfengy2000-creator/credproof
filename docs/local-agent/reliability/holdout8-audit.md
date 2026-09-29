# 新 8 例一次运行审计

审计对象：[20260929t095000z-holdout8](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/results.json)。只读核验，没有重跑模型、执行候选或修改原记录。自然语言评价属于 **Codex 语义自审，不是独立人工盲审**。案例是开发者构造并预先登记的模板留出合成案例，4 个泄露、4 个正常，不代表真实项目总体。

结构化逐案证据见 [holdout8-audit.json](../../../experiments/local-agent-pilot/reliability/holdout8-audit.json)。三次运行的 78 行原始案例/方法汇总见 [combined-audit.csv](../../../experiments/local-agent-pilot/reliability/combined-audit.csv)：包含运行标识、调用和 token、耗时、原始诊断/疑虑、实际修改、任务状态、对象判决及反馈。原 6 例两次重复运行没有当作新增样本合并。

## 1. 完整性和结论边界

[监督器](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/supervisor-result.json)记录 `complete=true`、比较子进程 exit 0；30 行结果完整，运行结束时 `frozen_inputs_unchanged=true`。30 行由 A/B/C 各 8 行及 h01/h03 上 D 各 3 次组成，不是 30 个独立案例。

读取本轮 493 个公开 JSON/JSONL/Python 文件，逐行核对聚合结果、方法结果、对象摘要与最后选定候选，没有发现不一致。未检出完整 `CP_EXEC_` 加 48 位十六进制的执行凭据；这仅是指定合成标记检查，不是通用秘密扫描，没有读取私有执行目录。

本轮 [34 文件冻结表](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/frozen-inputs.json)中的 `reliability.py` 摘要是 `8a3a0cebc683434c6690250a8d75a5a4accb7eb08c163cfdb7f000015a91635a`。审计时当前该文件已变为 `5b64b5e2b9067cd57dd9f5f31a010c6d14a43ab2c394cdb1f3e315276a66d7dd`，其余 33 文件匹配。后续源码修订不属于本次已测实现；不能用它修补本轮成绩，也不能把运行后变化倒推为运行期冻结失败。

## 2. 分开看任务完成和最终对象

| 方法 | 泄露例合格修复 | 正常例最终 PASS | 最终对象 PASS | 执行器任务完成 | 系统初始确认 | 正常系统误确认 | 正常实际修改 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A 固定规则 | 3/4 | 4/4 | 7/8 | 7/8 | 4/4 | 0/4 | 0/4 |
| B 一次输出 | 1/4 | 4/4 | 5/8 | 4/8 | 4/4 | 0/4 | 0/4 |
| C 工具反馈 | 4/4 | 4/4 | 8/8 | **6/8** | 4/4 | 0/4 | 0/4 |
| D 无候选反馈 | 0/6 次尝试 | 不适用 | 0/6 | 0/6 | 6/6 次尝试 | 不适用 | 不适用 |

系统初始确认来自所有方法共用的固定真实执行条件，不是模型自主发现率。C 修复更多泄露例，但任务完成数低于 A；不能只挑“最终 8/8 PASS”作为总成功率。每个正常例通过的都是保留原件，不能称为成功修复。

正常诊断需要进一步拆分：

- A 的 h05 `initially_leaking=true` 并生成拟议改动，被共同授权门槛拒绝。这是**固定规则误判 1/4**，不是 LLM 误报。
- B 原始语言没有明确断言正常例存在实际凭据泄露，观察到的明确误报 0/4；h08 有错误倾向的潜在风险猜测，单列疑虑 1/4。h07 外层 JSON 不合法，结构化诊断仍为 UNKNOWN，不能用人工可读文本回填。
- C 没观察到对正常例的明确凭据泄露确证，但 h05/h06 **没有有效诊断**。应写“已见明确误报 0，另有 2/4 诊断缺失”，不能写成四个正常例均正确诊断。h07/h08 曾提出疑虑，疑虑 2/4，最后没有确认泄露或提交修复。
- B 在 h05/h06/h08 各有一份被拒提案；与原件比对，仅少末尾换行，AST 相同，不能算三次实质无谓修复。A h05 的拟议修改则是实际规则变换，但未落成候选；所有方法的正常实际修改均为 0/4。

## 3. h05/h06 C：连 read_code 都未执行

[h05 原始模型响应](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/C-agent/model/model-01-response.json)和 [h06 原始模型响应](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/C-agent/model/model-01-response.json)均只含 `<function=read_code>…</tool_call>` **普通文本**，没有 native `tool_calls`，`finish_reason=stop`。

两例 `tool_trace=[]`、`verifications=[]`，模型各调用 1 次后结束。故不能描述成“读完源码但漏验收”，实际连 `read_code` 都没有调用。模型层 `COMPLETED` 只表示响应结束，执行器任务都是 `INCOMPLETE`。独立最终检查保留的安全原件通过 13 条条件，只能说明对象合格，不能追认 Agent 完成。审计没有解析这些标签去替模型执行工具。

## 4. h03：真实反馈改善，错误因果解释也必须保留

[h03 C result.json](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json)提供了本轮唯一一个真实的失败候选改进链，索引从 0 开始：

1. `tool_trace[3]` 提交 [candidate-1.py](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-1.py)。它把字符串 `credential=` 替换为 `credential=[REDACTED]`，却没有删除后面的动态凭据值。
2. `tool_trace[4]`、native `call_cpjy5xro` 对该候选检查 13 项，返回 FAIL，原因 `CREDENTIAL_LEAK`、通道 logging；其中 2 项失败，正常行为检查通过。
3. 该回执真实进入下一次 [model-06-request.json](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/model/model-06-request.json) 的 `messages[11]`。`model.messages[13]` 明确承认第一份补丁仍失败，随后提交第二份。
4. 但其解释不准确：模型说即使凭据值被替换，保留字面 `credential=`、透露曾处理凭据也算泄露。真实失败原因是**完整动态值仍在**，不是这个单词。不可把这段写成正确的根因推理。
5. `tool_trace[5]` 的 [candidate-2.py](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/candidate-2.py)改为固定消息，`tool_trace[6]` PASS，最终复验也 PASS。固定消息仍含 `credential processing error`，进一步说明裁判检查的是实际值，而不是字面词语。

因此可以报告 **1/1 次实际失败候选机会在反馈后形成合格后续候选**；只能支持这一条观察，不能据此估计稳定成功率。A 在 h03 的第一份补丁已经 PASS，不能宣称 C 在此案例优于 A。h03 的额外受控测试命中了初始条件缓存，不是重新触发的一次独立执行。

## 5. 每案例、每方法证据

P/F 表示最终对象 PASS/FAIL；没有注明未完成的单元格均记录执行器完成。

| 案例与结构 | A | B | C |
| --- | --- | --- | --- |
| h01 凭据跨 helper 参数进入日志 | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/A-fixed/result.json)；返回脱敏未覆盖日志 | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/B-once/result.json)；仅格式变化 | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/C-agent/result.json)；日志参数替换为标记，认证仍传真实执行凭据 |
| h02 denied 分支嵌套 stdout | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h02/C-agent/result.json) |
| h03 异常经两层 helper 进入日志 | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/A-fixed/result.json)；首候选通过 | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/B-once/result.json)；保留动态异常详情 | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent/result.json)；首候选 FAIL，第二份 PASS |
| h04 debug 列表构造器返回凭据 | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/A-fixed/result.json) | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/B-once/result.json)；识别问题却返回原代码 | [P](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h04/C-agent/result.json)；有有效新触发和返回脱敏 |
| h05 正常授权适配 helper | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/A-fixed/result.json)；规则误提案被拒 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/B-once/result.json) | [P、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h05/C-agent/result.json)；无真实工具调用 |
| h06 正常公共错误工厂 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/A-fixed/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/B-once/result.json) | [P、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h06/C-agent/result.json)；无真实工具调用 |
| h07 正常结构化日志脱敏 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/A-fixed/result.json) | [P、未完成](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/B-once/result.json)；JSON 引号转义错误 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h07/C-agent/result.json)；两次有效额外检查 PASS |
| h08 正常公开 debug 结构 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/A-fixed/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/B-once/result.json)；保留潜在风险猜测 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h08/C-agent/result.json)；三个错误候选 ID 被拒，最后验证原件 |

h01 是 C 在本组中完成而 A 未完成的具体例子；B/D 虽用文字识别日志问题，却没有实质改变泄露位置。该个例说明当前固定变换存在覆盖缺口，不足以证明对任意工具或项目的优势。

## 6. D 全部尝试与实耗

六次 D 都实际调用模型、输出可解析 JSON、形成候选，但与各自原件 AST 相同，只有空白/换行变化，最终均 `CREDENTIAL_LEAK`、logging 通道 FAIL。它们没有候选验证反馈，不能事后挑最好或让裁判代修：

- h01：[种子 1](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/D-no-feedback-1/result.json)、[种子 2](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/D-no-feedback-2/result.json)、[种子 3](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h01/D-no-feedback-3/result.json)。原始凭据参数仍进入日志。
- h03：[种子 1](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/D-no-feedback-1/result.json)、[种子 2](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/D-no-feedback-2/result.json)、[种子 3](../../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/D-no-feedback-3/result.json)。异常文本仍未经处理进入日志。

| 方法 / 分母 | 模型调用 | prompt tokens | completion tokens | 方法总墙钟秒 |
| --- | --- | --- | --- | --- |
| A / 8 例 | 0 | 0 | 0 | 33.538 |
| B / 8 例 | 8 | 12567 | 4634 | 57.178 |
| C / 8 例 | 31 | 99142 | 6648 | 74.335 |
| D / 6 次 | 6 | 9567 | 3428 | 43.188 |

墙钟取 `elapsed_s` 加总，包含方法内诊断/验证，不能当作纯推理耗时，也没有重复测量置信区间。共同 h01/h03 上 C 是 11 次调用、39265 输入 / 2968 输出 tokens，D 是 6 次调用、9567 输入 / 3428 输出 tokens。最大允许输出额相同，不代表实际总预算、上下文或计算量精确匹配。

可用于作品说明的审慎陈述是：本次模板留出合成测试中，C 在四个泄露例全部形成合格修复，其中一个有真实失败反馈后的改进；同时两个正常例因工具调用输出格式失败而未完成任务。系统没有把未经证实的正常修改写入候选。有限案例、共享初始诊断、语义自审及模型错误解释限制了结论，不能宣称完整自主诊断已解决或普遍优于固定方法。
