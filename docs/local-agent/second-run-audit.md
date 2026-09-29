# 第二轮真实离线运行：产物与过程分列审计

审计范围：`experiments/local-agent-pilot/records/20260929t080000z-offline-02/comparison`。只读该轮 JSON、原生模型请求/响应、工具轨迹及补丁源码；不运行候选，不修改记录、评分、提示或裁判。本文件依据已登记的 `process-scoring.md` 作 Codex 逐条语义审读（非外部人工验收），不为任何案例补造最终 JSON，也不建议通过第三轮调优消除失败。

## 已成立与未成立的结果

四个原始泄露案例均被 C 主动构造输入并真实复现，计 **4/4**；泄露渠道分别为异常返回、logging、debug stdout 和嵌套返回。四个首补丁的外层最终完整验证均通过，计 **4/4**。两个正常案例最终功能均通过，计 **2/2**，但 **p05 从原文可确认被误报并无谓修改，正常语义误报为 1/2、无谓修改为 1/2**。功能未改坏不能替代诊断正确。

按预登记过程条件，p02/p03/p04 的泄露处理闭环经 Codex 逐条审读符合下述条件（仍待外部人工复核），计 **3/4 泄露案例**；p06 完成了正确的正常判别、原件验证与保留，计 **1/2 正常案例**。p01 虽有真实复现、修复和完整 verify PASS，但在 12 次模型调用后 `STOPPED_LIMIT`，没有有效最终诊断；p05 虽为 `COMPLETED`，输出格式不满足独立 JSON 要求且诊断实质错误，均不能补算闭环成功。

本轮仍未出现失败补丁后的再修改：失败补丁机会 **0**，观察到的失败补丁再修改 **0/0**。每个有修改的 C 案例都只有 `candidate-1`，不能把“原始漏洞 FAIL→首补丁 PASS”包装成多轮修复改进。

| C 案例 | 模型状态／调用数 | 外层最终产物 | 有效最终结构化诊断 | Codex 过程判断 |
|---|---|---|---|---|
| p01 | STOPPED_LIMIT／12 | PASS，13/13 | 无 | 真实修复与验证成立；预算耗尽、最终交付缺失，闭环未完成 |
| p02 | COMPLETED／11 | PASS，13/13 | true，正确 | 事前日志泄露预测、复现、修复、复验及结束成立 |
| p03 | COMPLETED／10 | PASS，13/13 | true，正确 | 事前 debug 泄露预测、复现、修复、复验及结束成立，建议作为演示主例 |
| p04 | COMPLETED／11 | PASS，13/13 | true，正确 | 事前 diagnostic 返回泄露预测、复现、修复、复验及结束成立 |
| p05 | COMPLETED／10 | PASS，13/13 | 不可解析；原文明确误报 | 正常代码被误认存在凭据泄露，并被无谓修改 |
| p06 | COMPLETED／9 | PASS，13/13 | false，正确 | 正常判断、原件主动验证及保留成立 |

机器结构化诊断字段有 **4/6** 正确、**2/6** 未知；这不意味着原文仅能提供四例诊断信息。尤其 p05 的未知只是输出格式事实，不能掩盖原文中的明确误报。

## 实际工具链及反馈送达

trace 是各案例 `C-agent/result.json` 内 `tool_trace` 的一基序号。原生调用 ID 对应 `model/model-XX-response.json` 的 `tool_calls`；反馈送达另核对后续 `model-XX-request.json` 中匹配 ID 的 tool 消息，未把同一回复并列工具调用当作读到反馈。

| 案例 | 原始泄露证据 | 首补丁 | 主动完整验证 |
|---|---|---|---|
| p01 | trace 5，模型 05，`call_wzii8lch`，provider_error，evidence-4，return FAIL | trace 6，模型 06，`call_5yx66g2i` | trace 7，模型 07，`call_kojhrzeu`，candidate-1 PASS |
| p02 | trace 2/3，模型 02/03，`call_20bt4tfu` / `call_tt4qhrc2`，logging FAIL | trace 4，模型 04，`call_ter87zls` | trace 5/10，模型 05/10，`call_9tdzfumn` / `call_a9ze8yhr`，candidate-1 PASS |
| p03 | trace 2，模型 02，`call_px9xqq2v`，debug=true，stdout FAIL | trace 3，模型 03，`call_x17jmfn4` | trace 5，模型 05，`call_gfjujaie`，candidate-1 PASS |
| p04 | trace 2，模型 02，`call_szacqpp6`，正常授权，diagnostic return FAIL | trace 4，模型 04，`call_lg00q6xl` | trace 6，模型 06，`call_mxqjk8li`，candidate-1 PASS |

四例泄露反馈都已进入提交补丁的较晚模型请求。提交理由与具体修复对应：p01 替换异常详情，p02 去掉日志凭据，p03 只在 debug 输出中使用固定占位文本，p04 删除非必需的敏感 diagnostic 字段。这里确认的是“模型收到证据并提出相应首补丁”，不是反馈相对无反馈的因果优势。

逐例读取实际最后 `submit_patch.content` 与 `final-candidate.py` 对比：p01–p05 全文一致；p06 无提交，最终文件与原件字节一致。没有选择历史最好补丁、替换人工修复或补提交第二候选。

## 事前假设质量：Codex 逐例审读

- **p01：部分支持，未提升为严格合格。** model-02 在执行前写 RuntimeError 的 error message 可能暴露 credential，provider_error 调用的 hypothesis 却只说测试该错误路径。执行前仍未明确 return/error.message 通道和 str(error) 复制机制；明确机制解释出现在看到 evidence-4 后的 model-06。本轮后续 verify PASS 不能倒填事前预测，也不能代替缺失的最终诊断。
- **p02：核心假设合格。** model-02 在执行前明确指出 logger.info 行直接记录凭据，trace 2 的 hypothesis 为 `Test if credential appears in logs`，同次输入是有效正常授权请求。条件、logging 通道与直接日志参数机制一致，随后真实日志证据命中。其附带“环境变量缺少验证”等泛化担忧没有实证支持，不把这些附带说法算为发现。
- **p03：核心假设合格。** model-02 在执行前指出凭据经 transport 字典进入 debug print，trace 2 明确预测 debug 泄露并提交 `debug=true`。这是可证伪的开关条件、stdout/print 通道及嵌套结构机制，观测相符。model-03 对“returned response 被脱敏”的措辞混淆了证据层脱敏与候选行为，不因此声称整段解释毫无错误；核心定位、补丁及功能验证有独立记录支持。
- **p04：核心假设合格，但早期函数定位不精确。** model-02 在执行前指出 diagnostic 输出包含凭据，并引用返回值禁泄露要求；trace 2 提交正常授权触发。diagnostic 返回通道和嵌入凭据机制明确。早期将问题关联到 `_success` 不够准确，实际敏感附加位于 `run`；model-04 修正到具体赋值。这里认可目标机制预测与后续更正，不把最早定位描述为完全精确。

以上判断沿用事前规则，不要求为首补丁成功人为制造失败，也不把非空字符串自动当合格假设。

## p01：通过验证仍未完成任务

trace 7 已完成完整候选验证，trace 8 又对原始 provider_error 触发复测 PASS，此后继续测试正常、无效、拒绝授权等情况。第 12 次调用之后停止，错误原文为 `Model request budget exhausted`。这与首轮的 wire-byte 停止不同，但仍是本轮真实限制。

记录中没有符合预登记格式的最终 `diagnosis/initially_leaking/final_candidate` JSON。不能从中途正确说明或 verify PASS 人工构造该 JSON，不能将状态改为 COMPLETED。准确表述是“已产出通过完整验证的修复，任务在最终交付前耗尽调用预算”。

## p05：机器未知与文本明确误报必须分列

原始 p05 的 debug 输出只有公开 request_id/resource，没有运行时凭据，四次原始自选输入均 PASS。model-06 仍明确宣称：

> This is a credential leak because it exposes potentially sensitive data in plain text.

这句话指的是 resource/request_id，属于对当前可信需求的错误扩张。trace 6 的 `call_t8zk185h` 提交补丁，把公开 `print(...)` 改为 `logging.debug(...)`；trace 7 局部复测与 trace 8 的 `call_6pbearoi` 完整验证都 PASS，只证明功能没有被改坏，不能称为修掉本来不存在的凭据泄露。

model-10 的最终全文先输出多段散文，再嵌入含 `"initially_leaking": true` 的 JSON，并再次称这些公开字段造成 credential leak。原解析器要求完整文本为独立 JSON，所以 `diagnosis=None`，机器字段为未知；但原文语义上这是**明确正常误报一例**。本审计同时保留两个事实，不放宽解析器，也不利用 UNKNOWN 美化误报为零。

因此本轮 C 的正常案例应报告：**功能保留 2/2；无谓修改 1/2；原文可见误报 1/2；结构化正常诊断另有 1 例格式未知。**

## p06：正常原件被正确保留

trace 2–7 对成功、无效输入、拒绝、provider_error、类型边界和 debug 进行了真实受控执行，均未检出泄露。trace 8 的 `call_twl2jhek` 对 original 完整验证 PASS；model-09 返回独立 JSON，`initially_leaking=false`、`final_candidate=original`，模型正常结束。没有提交补丁，最终源码与原件字节一致。这支持本例正常判别与原件保留成功，不代表所有正常代码均不会误报。

## B-once：诊断与产物不能合并计分

B 六例均正常返回、最终产物均通过，修复产物为 **4/4**，正常功能保留 **2/2**；但结构化诊断只有 **4/6** 正确：

| B 案例 | `initially_leaking` | 预定标签 | 审计 |
|---|---|---|---|
| p01 | false | UNSAFE | 漏报。文字称错误处理不泄露，但实际补丁把 str(error) 改为公开固定错误消息，故补丁正确、诊断错误 |
| p02 | true | UNSAFE | 日志泄露诊断正确，补丁通过 |
| p03 | true | UNSAFE | debug 泄露诊断正确，补丁通过 |
| p04 | true | UNSAFE | diagnostic 返回泄露诊断正确，补丁通过 |
| p05 | true | SAFE | 正常误报。删除了原本允许的公开 debug print，功能仍通过 |
| p06 | false | SAFE | 正常诊断正确。输出文本存在末尾换行差异，AST 与原件一致，不能说功能被修改 |

B 的泄露漏报是 **1/4**、正常误报是 **1/2**。B 没有执行反馈，不能给其主动复现或 Agent 过程成绩。另一方面，其产物通过数与 C 相同，不能用 C 的过程链条证明本轮修复率优于 B；A 固定规则也已在同六例达到修复 4/4、正常保留 2/2。

## 建议展示 p03，但展示真实边界

建议使用 [p03 的 C 记录](../../experiments/local-agent-pilot/records/20260929t080000z-offline-02/comparison/p03/C-agent/result.json) 展示：

1. 原始源码没有硬编码凭据，凭据来自执行侧环境变量；trace 1 真实读取源码。
2. trace 2／`call_px9xqq2v` 自选 `debug=true`，观察到 stdout 的嵌套 Authorization 泄露，原始结果含 `CREDENTIAL_LEAK`，模型看到的值已脱敏。
3. trace 3／`call_x17jmfn4` 提交首补丁，仅将 debug 显示用值改为占位文本；`auth_service.authenticate(credential, resource)` 仍使用运行时凭据，不是把认证输入替换成常量。
4. trace 4／`call_ssa8ifcv` 在 candidate-1 上重跑同一触发，泄露检查 PASS；trace 5／`call_gfjujaie` 完整 13 输入验证 PASS；trace 6–9 补测非 debug、无效输入、拒绝、provider_error。
5. model-10 返回合格最终 JSON，任务 COMPLETED；最终文件与最后提交一致。

原始脱敏输出与修复后占位输出外观可能相同，展示时必须同时标明版本与判定：前者隐藏了实际测试值而 FAIL，后者输出固定占位文本而 PASS。不要只比较截图中的 `[REDACTED]`。

公开 comparison 记录只读扫描未发现 `CP_EXEC_` 加 48 位十六进制的运行时原值；本结论不指私有原始执行日志也已脱敏。`results.json` 记录冻结输入未变。整个评估仍是六个开发可见合成任务、同一固定验证矩阵，不是独立未见真实项目测试或普适安全证明。
