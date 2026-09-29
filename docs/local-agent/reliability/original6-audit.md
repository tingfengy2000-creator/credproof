# 原 6 例两轮可靠性复测审计

审计日期：2026-09-29。本次只读既有记录和源码，未运行模型、候选或补测。逐案结构化结果见 [original6-audit.json](../../../experiments/local-agent-pilot/reliability/original6-audit.json)；自然语言含义由 **Codex 自审，非独立人工评审**。以下两个运行是同一组开发可见案例的重复运行，不是 12 个独立案例，也不是留出成绩。

结论：两轮 A 和 C 都修复 4/4 个泄露案例、保留 2/2 个正常案例。压缩轮 C 仍对 p05 作出无依据的安全泄露判断并尝试修改，系统拒绝了提案；最终 `initially_leaking=false` 不能抹去前面的错误。尚无 C 的“失败候选→利用反馈→后续候选通过”实例。压缩轮全局退出码为 **1**，不能作为整包冻结成功的运行发布。

## 1. 运行完整性与版本边界

| 运行 | 记录数量 | 监督器与冻结结果 | 可用范围 |
| --- | --- | --- | --- |
| [093000 原输入轮](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/supervisor-result.json) | 24 行：A/B/C 各 6，D 为 p01/p03 各 3 次 | 子进程 exit 0，`complete=true`，`frozen_inputs_unchanged=true` | D 六次均在请求前被预算门槛拒绝；不可当作六次模型修复失败 |
| [094000 压缩输入轮](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/supervisor-result.json) | 24 行完整保存 | 子进程 **exit 1**，`complete=false`，`frozen_inputs_unchanged=false` | 可引用逐案记录，但必须附“核心执行文件在哈希复核中一致，非整包冻结成功”的限制 |

对压缩轮 [23 文件起始冻结表](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/frozen-inputs.json)逐项复核，只有 `agent_pilot/bundle.py` 和 `agent_pilot/web.py` 与冻结值不同，其余 21 个一致。两者在运行期间被并行开发，而冻结逻辑对顶层全部 `*.py` 做了广泛哈希检查。完整旧值、新值记录在审计 JSON 中。

静态检查本地导入闭包：`reliability → experiment/fixed/judge/model_client/tools`，`experiment → isolation → sandbox_runner`；监督器 `offline_run` 和握手 `handshake` 分别使用 `tools`、`model_client/tools`。这 10 个文件均匹配压缩轮冻结值，没有导入 `bundle` 或 `web` 的路径。此结论来自源码和哈希比较，**不是运行期持续监控或第三方认证**，也不能改写实际 exit 1。原输入轮的 `reliability.py` 与当前版本不同，是随后压缩输入的版本变化；其运行结束时冻结成功的原记录仍保留。

逐行比较了两轮合计 48 个方法结果与聚合记录、原件/最终文件摘要和最后选定对象，未发现不一致。读取原输入轮 329 个、压缩轮 406 个公开 JSON/JSONL/Python 文件，未检出完整 `CP_EXEC_` 加 48 位十六进制的执行凭据。该检查只覆盖此合成标记，不等于通用秘密审计；没有读取执行侧私有目录。

## 2. 计数口径与每方法结果

“合格修复”要求泄露案例的实际选定候选通过 13 条最终条件；“任务完成”读取执行器状态，不能用最终复验 PASS 替代。正常例分母为 p05/p06；D 只有两个泄露案例的六次尝试，不含正常例。所有方法共享三个实际初始诊断条件，系统确认不等于模型独立发现。

| 运行 / 方法 | 最终对象 PASS | 泄露例合格修复 | 正常例最终 PASS | 预算内任务完成 | 系统误确认 / 正常例 | 实际不必要修改 / 正常例 |
| --- | --- | --- | --- | --- | --- | --- |
| 原输入 A | 6/6 | 4/4 | 2/2 | 6/6 | 0/2 | 0/2 |
| 原输入 B | 5/6 | 3/4 | 2/2 | 4/6 | 0/2 | 0/2 |
| 原输入 C | 6/6 | 4/4 | 2/2 | 6/6 | 0/2 | 0/2 |
| 原输入 D | 0/6 | 0/6 次尝试；0 次模型调用 | 不适用 | 0/6 | 不适用 | 不适用 |
| 压缩 A | 6/6 | 4/4 | 2/2 | 6/6 | 0/2 | 0/2 |
| 压缩 B | 5/6 | 3/4 | 2/2 | 5/6 | 0/2 | 0/2 |
| 压缩 C | 6/6 | 4/4 | 2/2 | 6/6 | 0/2 | 0/2 |
| 压缩 D | 1/6 | 1/6 次尝试 | 不适用 | 1/6 | 不适用 | 不适用 |

A/B/C 各自的系统初始泄露确认均为 4/4；这主要说明固定公共诊断条件覆盖了这四个构造案例。A 是规则程序，没有模型误报率。B 两轮均未在正常例原始语言中断言凭据泄露，语义误报为 0/2；C 原输入轮为 0/2，压缩轮有 **1/2 个正常例发生错误安全确证和无依据修改尝试**。该 1/2 不是“输出中真的出现凭据”，也不等于最终结构化字段错误，详见下一节。

## 3. p05：不能用结尾的 false 隐藏过程错误

压缩轮 [p05 C result.json](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p05/C-agent/result.json) 的索引均从 0 开始：

1. `model.messages[3]` 和 `[6]` 的假设是 **“Debug output might leak credential information”**。第一次给了不存在的 `candidate_id=test-1`，被拒；第二次实际执行原件。
2. `tool_trace[2]` / `evidence-4` 返回 PASS、空泄露通道。输出只有模型自行提供的公开 `resource=secret-resource` 与 `request_id=test-123`；字段名或内容听起来敏感，不会改变契约把它们定义为公开输入的事实。
3. 收到上述 PASS 后，`model.messages[8]` 写道 **“I've confirmed my hypothesis. The debug output is indeed leaking information through stdout.”**，随后将 resource/request ID 称为 sensitive information。确认段字面说的是“信息泄露”，并未再次明确声称匹配到完整运行时 credential；但它承接前面的凭据假设，对明确允许的公开字段作出错误安全确证。故计作 1 个过程误报/无依据修复案例，不伪造“检测到了真实凭据”的说法。
4. `tool_trace[3]` / native `call_nifl94qa` 提交删除 debug print 的实质补丁，执行器因 `no_current_confirmed_leak_evidence` 拒绝，没有写入候选。拒绝反馈真实出现在下一份 [model-05-request.json](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p05/C-agent/model/model-05-request.json) 的 `messages[9]` 中。
5. 模型随后承认提案被拒，却仍保留“could be considered a security concern”的措辞；最后 `tool_trace[4]` 验证原件并填 `initially_leaking=false`。这是**行为上退回原件**，不是充分的语义撤回，也不是失败补丁迭代成功。最终文件与原件相同，实际不必要修改为 0。

原输入轮 [p05 C](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p05/C-agent/result.json) 则明确判断无泄露，无提案，直接验证原件。

B 的 p05 两轮都明确说明 debug 输出只是公开信息、没有凭据泄露。虽然各有一份被拒提案，但比对 `diagnosis.code` 与 `original.py`，仅缺少末尾换行，`strip()` 和 AST 均相同。压缩轮 p06 B 也是同一情况。因此 B 的拒绝数为原输入 1/2、压缩 2/2 正常例，**不能等同于模型误报或实质无谓修复**。C 压缩轮的拒绝则确实阻止了删除公开调试输出的实质提案。

## 4. 原 6 例逐案入口

表中 P/F 是最终对象 PASS/FAIL；“未完成”单列，避免混淆。

| 原输入轮 | A | B | C 与过程限制 |
| --- | --- | --- | --- |
| p01 异常返回 | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/C-agent/result.json)；两次额外触发被拒，使用共享证据 |
| p02 logging | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p02/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p02/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p02/C-agent/result.json)；额外触发被拒 |
| p03 嵌套 debug stdout | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/A-fixed/result.json) | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/B-once/result.json)；非法 JSON，无候选 | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/C-agent/result.json)；读取共享证据后修复 |
| p04 嵌套返回 | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p04/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p04/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p04/C-agent/result.json)；先验证原件 FAIL；最后错误填原始状态 false |
| p05 正常公开日志 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p05/A-fixed/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p05/B-once/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p05/C-agent/result.json) |
| p06 正常错误处理 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p06/A-fixed/result.json) | [P、未完成](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p06/B-once/result.json)；非法 JSON，保留安全原件 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p06/C-agent/result.json) |

原输入 p04 C 的 `messages[2]`、`[6]` 正确识别原件泄露，最后 `[10]` 却将 `initially_leaking` 填为 false，实际上在描述修复后的状态。必须同时保留“前文正确”和“最终字段错误”；不能算全程诊断无误。

| 压缩轮（非整包冻结成功） | A | B | C 与过程限制 |
| --- | --- | --- | --- |
| p01 | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/C-agent/result.json)；额外有效触发真实复现 return 泄露 |
| p02 | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p02/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p02/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p02/C-agent/result.json)；第二次触发与初始条件相同，命中缓存 |
| p03 | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/A-fixed/result.json) | [F、未完成](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/B-once/result.json)；非法 JSON | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/C-agent/result.json)；使用共享 stdout 泄露证据 |
| p04 | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p04/A-fixed/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p04/B-once/result.json) | [P](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p04/C-agent/result.json)；无额外触发，使用共享证据 |
| p05 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p05/A-fixed/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p05/B-once/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p05/C-agent/result.json)；有过程误报和被拒实质提案 |
| p06 | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p06/A-fixed/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p06/B-once/result.json) | [P、未改](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p06/C-agent/result.json)；三次不存在候选被拒，第四次有效测试 PASS |

因此不能写成“C 主动重新执行并复现了四种泄露”。原输入轮四个泄露案例的额外受控触发均因错误候选 ID 被拒；压缩轮仅 p01 是新的实际泄露复现，p02 复用缓存，p03/p04 依赖共同初始真实证据。允许使用已有充分证据进行修复，但应如实描述证据来源。

## 5. D 的全部尝试及公平性

原输入轮六次均 `STOPPED_LIMIT`、0 次模型调用、没有候选。p01 首请求保守字节上界 8892，p03 为 9415，均超过为 8192 输出预留后的 7680 输入上界；不是模型上下文实际 token 数测量。保留原件的最终 FAIL 属于原件仍有泄露，不是模型生成了失败补丁：

- p01：[种子 1](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/D-no-feedback-1/result.json)、[种子 2](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/D-no-feedback-2/result.json)、[种子 3](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p01/D-no-feedback-3/result.json)。原件 FAIL 原因为 `CREDENTIAL_LEAK`、`RESPONSE_CONTRACT`。
- p03：[种子 1](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/D-no-feedback-1/result.json)、[种子 2](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/D-no-feedback-2/result.json)、[种子 3](../../../experiments/local-agent-pilot/reliability/20260929t093000z-original6/comparison/p03/D-no-feedback-3/result.json)。原件 FAIL 原因为 `CREDENTIAL_LEAK`。

压缩轮各实际调用一次模型：

| 案例 / 种子 | 实际结果与原因 |
| --- | --- |
| [p01 / 1](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/D-no-feedback-1/result.json) | FAIL；语言识别问题，但候选仅少末尾换行，保留 `str(error)`；凭据泄露与错误消息契约均失败 |
| [p01 / 2](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/D-no-feedback-2/result.json) | PASS；把 `str(error)` 改为固定错误消息 |
| [p01 / 3](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p01/D-no-feedback-3/result.json) | FAIL；与种子 1 相同的实质未修复 |
| [p03 / 1](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/D-no-feedback-1/result.json) | 非法 JSON，无候选；保留原件，最终凭据泄露 FAIL |
| [p03 / 2](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/D-no-feedback-2/result.json) | 非法 JSON，无候选；同上 |
| [p03 / 3](../../../experiments/local-agent-pilot/reliability/20260929t094000z-original6-compact/comparison/p03/D-no-feedback-3/result.json) | 非法 JSON，无候选；同上 |

B 两轮 p03、原输入 B p06、压缩 D 三个 p03 均在 JSON 字符串中直接放入换行，解析报 `Invalid control character`。原始文字可以读出对泄露/安全的判断，但执行器不能据此假造有效结构化结果或自行修补响应。此类失利主要体现输出协议可靠性，不能据此证明 C 的漏洞理解全面优于 B/D。

预算上限 C 为 12×2048，D 为每案例 3×8192，最大输出总额同为 24576；**实际调用、输入和输出均不匹配**。以下为服务端记录用量加总，含重复上下文，不是独立信息量：

| 运行 / 方法 | 模型调用 | prompt tokens | completion tokens |
| --- | --- | --- | --- |
| 原输入 B / 6 例 | 6 | 14493 | 2892 |
| 原输入 C / 6 例 | 26 | 100810 | 4632 |
| 原输入 D / 6 次 | 0 | 0 | 0 |
| 压缩 B / 6 例 | 6 | 9287 | 2970 |
| 压缩 C / 6 例 | 28 | 86207 | 5782 |
| 压缩 D / 6 次 | 6 | 9462 | 2864 |

仅比较共同的 p01/p03，压缩 C 使用 9 次调用、27816 输入和 2005 输出 tokens；D 使用 6 次调用、9462 输入和 2864 输出 tokens。不能写成精确等预算实耗的优越性结论，也不能挑选 D 最好一份代表所有尝试。

## 6. 反馈究竟改善了什么

两轮 C 的已提交失败候选数均为 0，因此“失败候选经反馈改好”为 **0/0 机会**，不是成功率 100%。原输入 p04 是验证原件 FAIL 后提交首个合格候选；压缩 p05 是无授权提案被拒后改为验证原件。后者可报告一次执行约束后的行为退回，但其安全疑虑没有完全撤回，不能算成功修复或充分纠正误报。

现有证据支持：真实本地模型可通过工具流程读取证据、生成候选，执行器能限制无依据修改并在验证通过时终止；在这六个构造案例上，固定方法同样取得 4/4 修复。证据尚不支持普适诊断能力、失败修复迭代收益、独立留出泛化、比规则方法更优，或压缩轮整包冻结成功。
