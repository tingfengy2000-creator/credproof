# 工具协议失败定位与有限纠正设计

核查日期：2026-09-29；起始实现 `65abca2ac6c531f2b790cf893da7a0c5ad166752`。这是 **Codex 辅助的内部源码审查与离线 REPLAY**，不是第三方/独立人工审计。没有新增模型调用，没有执行候选。本轮新实现由主任务负责，本文件不声称新提示已在真实模型上成功。

## 真实失败与精确回归输入

原记录来自 `experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/`：

| 案例 | 原始请求/响应相对上述目录 | 服务报告的 prompt / completion tokens |
|---|---|---|
| h05 | `h05/C-agent/model/model-01-request.json`、`h05/C-agent/model/model-01-response.json` | 1975 / 20 |
| h06 | `h06/C-agent/model/model-01-request.json`、`h06/C-agent/model/model-01-response.json` | 1972 / 20 |

两份原始响应的正文相同：

```text
<function=read_code>
<parameter=path>
tool.py
</parameter>
</function>
</tool_call>
```

缺少开头 `<tool_call>`；`message.tool_calls` 不存在，`finish_reason=stop`。请求确实携带 read_code 等 5 个 tools，输出上限 2048，远未用满。没有发生工具调度；旧客户端报告 COMPLETED 仅表示框架自然结束，任务仍 INCOMPLETE。失败应归为**调用格式文本回落、未产生原生工具调用**，不能记为成功读取代码、模型已完成正常诊断或预算耗尽。

原响应 SHA-256 分别为 `5b4b2a17429841dbedff36a5129989233c4e515caa5ee553e7badb97c2410dce`（h05）和 `ce552707835664d7c3a4c3cd2e712d8ca2ea11d349943a1d3fbc8a6dd0e129b3`（h06）。完整相对路径、请求哈希、状态和来源已保存于 [protocol-diagnosis.json](../../../experiments/local-agent-pilot/tool-call-revision/protocol-diagnosis.json)。两例均原样保留，没有替换历史响应。

## 对应版本的失败链

1. **服务配置匹配模型。** 实际本地 manifest/config 显示 parser 和 renderer 都是 qwen3-coder；已安装 Ollama 二进制 SHA-256 与 0.34.4 安装审计一致：`ad9c53441752620a2314a65a798a888d98df3636c8815ca044de591f82892ff4`。没有发现把它误配成普通 qwen3 parser 的证据。
2. **生成格式与 wire 协议是两层。** v0.34.4 renderer 将 API tools 转为供模型生成使用的 coder XML 格式，并要求完整外层标签；模型并不是直接生成 HTTP `tool_calls` 字段。[固定版本 renderer](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/model/renderers/qwen3coder.go)
3. **固定版本 parser 只由完整开头标签进入工具收集。** `eat` 的起始分支检查 literal `<tool_call>`，未命中时内容作为普通文本输出。本地响应的 bare `<function=...>` 形态与这条回落路径一致。[固定版本 parser](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/model/parsers/qwen3coder.go)
4. **客户端没有丢弃一个本来存在的 native call。** `from_ollama_response` 原样保留 content，仅把真实 tool_calls 转成 Qwen Message.function_call。对两份原响应调用该纯转换函数，输出均无 function_call。这一步是离线回放，不是推理。
5. **官方循环据此自然结束。** 已安装 Qwen-Agent 0.0.34：`llm/base.py:407` 的 raw_chat 传 tools；`agent.py:239` 的 `_detect_tool` 检查 function_call；`agents/fncall_agent.py:73` 在没有工具调用时 break。旧客户端于是收到普通最终文本并返回 COMPLETED。原生模式不再让另一套框架文本解析器解释这些标签。[官方 Qwen-Agent 说明](https://github.com/QwenLM/Qwen-Agent)

这定位到**模型输出格式与服务端解析的交界，叠加客户端把无动作文本当普通结束**。没有记录解析前的原始采样 token 流，所以不能声称已证明具体采样机制、缓存导致原因或某个模型权重错误；也没有证据表明切换 `/api/chat` 就能解决。当前兼容接口支持 tools，固定版本 wire 字段也包含 tool_calls/tool_call_id。[Ollama 兼容接口](https://docs.ollama.com/api/openai-compatibility)、[固定版本 wire 定义](https://raw.githubusercontent.com/ollama/ollama/v0.34.4/openai/openai.go)

## 一致协议与一次预算内纠正

继续使用 `use_raw_api=True`、固定本地 `/v1/chat/completions`、`stream:false`。只执行服务端返回的 native tool_calls；不从正文、XML、JSON 示例或代码块提取可执行指令，不猜工具名、不补 ID、不伪造执行结果。Qwen-Agent 官方调度循环继续保留。

只对 C 显式启用 `max_format_corrections=1`，默认 0。框架正常结束但可信执行器仍有必要检查未完成时，可以把**原输入＋完整既有输出＋固定格式提醒**交给同一 Assistant/client 继续。提醒要求遵循工具定义附带的调用格式、作出实际调用而非示例，并说明未执行的文本不能代表工具结果。不要写“禁止 XML、请直接输出 tool_calls”：这会与服务端 coder renderer 的内部生成格式相矛盾。若此前已真实执行过工具，提醒也不能概括宣称“此前没有任何工具执行”；可条件性说明“仅出现在文本中的调用没有执行”。

纠正共享原 12 次请求、900 秒任务、120 秒单请求、16K 上下文和 3 候选上限；不重建 client、不重置计数、不删除旧消息。`format_correction_attempts` 记录计划纠正次数，`format_correction_call_ids` 只列实际经过 `_request` 预算准入的纠正请求。无预算时允许有计划次数但无发送 ID，不把未发送请求算推理。

已完成的可信 terminal 立即结束；ERROR、超时和封存状态不发纠正。第二次仍自然结束且没有执行器完成则 INCOMPLETE；预算门先挡住时是 STOPPED_LIMIT。B/D 无工具对照不额外获赠一次请求。此改动支持一个统一的继续机制，不是保证模型修复成功的策略。

## REPLAY 回归与未证明事项

新增 [test_tool_protocol.py](../../../agent_pilot/test_tool_protocol.py) 共 15 项，使用真实 `_request`、适配器与官方 Assistant/FnCallAgent，但 HTTP 被内存 fixture 替代。首响应使用原 h05/h06 JSON；后续合法调用是明确标注的控制输入，工具只产生内存计数。日志中的模拟 model_calls 是测试计数，不能报告成新真实推理调用。

覆盖一次纠正后原生调用、先调用再文本结束后纠正的完整历史回灌（含 tool_call_id，旧工具不重派发）、重复文本不执行、总预算 1/2、不重置预算、完成前后不多调、超时晚到不执行、HTTP 错误不纠正、默认 0、无工具对照、未知工具拒绝、错误 JSON/字段类型/多余字段/越界路径拒绝。已运行以下命令，15 tests，exit 0：

```text
wsl --exec bash -lc 'cd /mnt/e/比赛/密证_CredProof-local-agent && /home/tingfeng/credproof-agent-runtime/venv/bin/python -B -m unittest agent_pilot.test_tool_protocol -v'
```

这些结果只证明已覆盖的协议与预算控制路径，没有证明纠正提示的模型有效率、修复质量或新8例成功率。后续真实评估需新的冻结版本和独立记录，旧 h05/h06 失败不能覆盖或改成成功。
