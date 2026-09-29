# 首轮真实离线运行的过程审计

审计对象仅为 `experiments/local-agent-pilot/records/20260929t074300z-offline-01/comparison`，对应保留提交 `cacfdda`。本次只读取该轮 JSON、模型原始请求/响应、工具轨迹及最终补丁；不执行候选，不修改原记录。后续输入预算修订或新一轮结果均不能补记本轮成绩。评分沿用 `process-scoring.md`，不事后放宽假设质量要求。

## 结论及计数

- C 在原始版本上主动构造输入并实际复现了 **4/4** 泄露案例：异常文本返回、日志参数、debug stdout、嵌套返回元数据。不是把外层 initial preflight 或隐藏矩阵触发算为 Agent 主动复现。
- 四例分别只提交一个 `candidate-1`，最终文件与最后提交全文一致。外层最终判定均为 13/13 PASS：泄露案例产物通过 **4/4**；正常案例产物通过 **2/2**，原件字节均未变。
- 六个 C 均为 `STOPPED_LIMIT`，原因都是保守的 **13824-byte** 请求门槛；没有有效最终诊断 JSON，没有 `verify_patch` 调用。按预登记规则，本轮完整 Agent 闭环成功**未成立**，不能把 6/6 产物 PASS 表述为 6/6 自主闭环成功。
- 失败补丁再修改计数为 **0/0（无失败补丁机会）**。四例都是“原始漏洞证据→首个补丁”，没有 `candidate-1 FAIL→candidate-2`，不能宣称观察到失败后迭代改进。

## 可复核的主动触发与版本链

下表 trace 为各 `pXX/C-agent/result.json` 中 `tool_trace` 的一基序号；模型调用号对应 `model/model-XX-response.json`。原生 ID 来自真实 `tool_calls`，不是由文字推测。

| 案例 | 原始泄露触发 | 原生调用 | 提交及版本 | 后续观测 |
|---|---|---|---|---|
| p01 | trace 5，`provider_error`，`evidence-4`；`return` 泄露及 `RESPONSE_CONTRACT` | 模型 05：`call_z3l25grp` | trace 6，模型 06：`call_5tquo3jt`，candidate-1 | 无模型主动补丁验证；外层最终 13/13 PASS |
| p02 | trace 2、3，正常授权输入，`evidence-1/2`；`logging` 泄露 | 模型 02：`call_hhv6by3r`；模型 03：`call_fbyrbjc2` | trace 4，模型 04：`call_32gxfbw3`，candidate-1 | 无模型主动补丁验证；外层最终 13/13 PASS |
| p03 | trace 2，`debug=true`，`evidence-1`；`stdout` 泄露 | 模型 02：`call_j1qbi75j` | trace 3，模型 03：`call_wl419eok`，candidate-1 | trace 4，模型 04：`call_fcxe4lbz`，在 candidate-1 上同一自选触发得到 PASS；仍没有完整 `verify_patch` |
| p04 | trace 2，正常授权输入，`evidence-1`；嵌套 `diagnostic` 返回泄露 | 模型 02：`call_1wsli1go` | trace 4，模型 04：`call_7gk509e3`，candidate-1 | trace 3 再次读原始源码；无模型主动补丁验证；外层最终 13/13 PASS |

逐例核对了提交所在模型请求中的 tool 消息：上述泄露反馈确实已进入后续模型调用，再产生首补丁，并非同一模型回复并列调用测试和提交、尚未读到测试结果。提交理由分别解释了异常公开消息替换、移除日志凭据、debug 结构使用占位文本、移除非必需 diagnostic 字段，与该轮证据相符。这支持“有证据后的首补丁”，不证明反馈的因果增益，也不证明多轮修复能力。

四份最终补丁 SHA256：

| 案例 | `final-candidate.py` 与最后提交内容的 SHA256 |
|---|---|
| p01 | `15021e8201ac09bb73a06b75f669e0c350f8240356e38d6ae0841f3d64db65c1` |
| p02 | `64ad1d5d3f5e9de94b71127434ef58569ef6a742f6900060a313cfe886c94d4b` |
| p03 | `ba662eb32c679a9ef9243d9dff1f050378a211529faa5311705d55ae720bb24c` |
| p04 | `704e4f51dab78ed36459965a475664d2830549c6581f54adb2b5ed7e6f6313ed` |

## p01 的事前假设只获得部分支持

`p01/C-agent/model/model-02-response.json` 在 provider_error 执行之前确有文字：

> The error handling for RuntimeError might expose the credential in the error message

因此不能说模型完全没有事前怀疑：它预先指出 RuntimeError 错误消息可能暴露凭据。随后 model-05 的实际工具参数选择了 `auth_mode=provider_error`，确实命中相关条件。

但该次 `hypothesis` 字段只是 `Test valid request with authentication provider error`。执行前文字未明确指出 **returned/error.message 通道**及 **str(error) 复制机制**；按预登记的“条件、输出通道、泄露机制”三个要素，事前明确性不足。不能把宽泛早期猜测自动认定为完整合格假设。

明确的“response 中包含 credential”、引用 `return {... "message": str(error)}` 以及解释复制机制，出现在 **model-06-response.json**，即已经看过 `evidence-4` 之后。这是有效的观测后诊断依据，但不能倒填成观测前预测。本项审计为**部分支持／严格假设质量未确认**；不调整机械汇总，也不给完整闭环加分。

## 正常案例与诊断边界

p05、p06 均没有提交补丁，最终源码与对应 fixture 字节一致。p05 的 trace 2–5 四次自选执行、p06 的 trace 2–6 五次自选执行均未检出凭据泄露。它们均未完成最终诊断 JSON 或主动完整验证，因此正式诊断指标应记未知，不能报“误报 0/2”。

p05 的 `model-03-response.json` 把公开允许的 resource/request_id debug 文本称作 “potential leak”。这是中途超出当前凭据泄露任务范围的判断，必须保留为定性问题；由于没有最终布尔诊断，不将其擅自转换为预登记的最终误报计数。p06 中途认为主要凭据处理正确，但同样不替代缺失的最终诊断。

## 证据脱敏与审计范围

模型可见的原始泄露观测均在对应敏感位置使用 `[REDACTED]`：p01 错误消息、p02 日志、p03 stdout 的 Authorization、p04 递归返回字段。只读扫描本轮公开 comparison 目录的 JSON/JSONL/Python/Markdown，未发现符合 `CP_EXEC_` 加 48 位十六进制格式的运行时原值。

这里的结论是**模型可见及本轮公开记录中的证据已脱敏**，不是私有执行日志也已脱敏。执行侧私有原始日志本来需要保留合成凭据用于独立判定，本审计未将其加入公开记录。

p03 修复前与修复后的可见 stdout 都可能显示相同 `[REDACTED]` 文本：前者是证据层遮蔽真实测试值且判为 FAIL，后者是补丁输出固定占位文本且判为 PASS。应同时核对 `candidate_id`、判定理由及源码版本，不能只看脱敏后的外观就认为两次执行相同。

本轮确有真实模型工具调用、主动触发和符合要求的首补丁，但完整复验、最终诊断与任务正常结束均缺失。上述不足保留在本轮记录中，等待新运行只能产生新的独立结果。
