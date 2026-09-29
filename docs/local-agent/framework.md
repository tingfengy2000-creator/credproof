# 本地 Qwen-Agent 框架与接口边界

核查与安装日期：2026-09-29。工作目录：`E:\比赛\密证_CredProof-local-agent`，WSL 对应 `/mnt/e/比赛/密证_CredProof-local-agent`。本文只说明客户端与安装证据，不将单元测试写成模型握手成功或凭据修复有效。

## 1. 采用的框架及实际安装

采用官方 PyPI 的 `qwen-agent==0.0.34`，保留官方 `Assistant → FnCallAgent` 的消息、工具结果回灌与循环调度。没有安装 `[rag]`、`[gui]`、`[code_interpreter]`、`[mcp]` extras，也没有安装或启用任意 shell、网络检索、文件浏览或 Python 执行工具。包内仍包含部分内置工具源码；**源码存在不等于被授权给模型**，客户端仅接受调用方显式创建的 `BaseTool` 实例，不接受工具名称字符串、配置字典或 MCP 配置。

正式实验解释器是 `/home/tingfeng/credproof-agent-runtime/venv/bin/python`，底层 WSL Python 3.12.3。系统缺少 pip，先用 `python3 -m venv --without-pip` 创建独立环境，再从官方 `https://bootstrap.pypa.io/get-pip.py` 引导 pip；没有使用全局 apt 或修改系统 Python。随后只从 `https://pypi.org/simple` 安装。Windows `.venv` 曾安装最小包，用于早期源码核查；后续未继续补齐，不作为正式运行环境。

实际发现并复现了最小安装的导入缺口：`utils.py` 无条件导入 `numpy`、`soundfile`；`tools/__init__.py` 导入 `python_executor.py`，后者需要 `tqdm` 与 `dateutil`。这四项没有出现在本次最小 wheel 的有效依赖安装中。因此仅补 `numpy==2.5.3`、`soundfile==0.14.0`、`tqdm==4.70.1`、`python-dateutil==2.9.0.post0`（带入 `six`）。未因此启用音频、执行器或 RAG 能力。

完整精确版本在 `agent_pilot/requirements-lock.txt`；其中还包括上游最小依赖带入的 `openai==3.20.0`、`dashscope==1.27.7` 等。它们被安装不代表使用云端：实际模型传输只使用标准库向固定本地地址发请求。

安装审计保存在忽略提交的 `runs/local-agent/setup/`：`windows-install-report.json`、`windows-numpy-install-report.json`、`linux-install-report.json`、`linux-required-imports-report.json`、`linux-required-tqdm-report.json`、`linux-required-dateutil-report.json`。pip 报告带每个 wheel 的来源 URL 与哈希；锁文件固定版本，但它本身不是跨平台 wheel 哈希锁。重建命令：

```bash
/home/tingfeng/credproof-agent-runtime/venv/bin/python -m pip install \
  --isolated --index-url https://pypi.org/simple -r agent_pilot/requirements-lock.txt
/home/tingfeng/credproof-agent-runtime/venv/bin/python -m pip check
/home/tingfeng/credproof-agent-runtime/venv/bin/python -m unittest agent_pilot.test_model_client -v
```

## 2. 官方接口与必要的适配

客户端文件为 `agent_pilot/model_client.py`。固定模型 `qwen3-coder:30b`，固定地址 `http://127.0.0.1:11435/v1`，实际发送 `POST /chat/completions`。`use_raw_api=True` 让 Qwen-Agent 使用原生 `tools/tool_calls`，不从回答文本中识别伪造的 `<tool_call>`。没有套用 vLLM 的命令行参数。

对安装后的 **0.0.34 wheel 源码**，本次核对了以下行为；GitHub main 仅作公开导航，不能代替已安装版本事实：

| 已安装源文件 | 相关行为 | 本项目处理 |
|---|---|---|
| `qwen_agent/llm/base.py` 的 `raw_chat` | 原生模式向生成配置加入 `tools`，要求 full stream 迭代接口 | 保留该入口及 `use_raw_api=True` |
| 同文件 `_conv_qwen_agent_messages_to_oai` | 把工具结果关联 ID 写入 `id` | 独立纯函数 `to_ollama_messages` 使用兼容 API 的 `tool_call_id`，保留服务器返回的调用 ID |
| `qwen_agent/llm/oai.py` 的 `_chat_no_stream` | 只转换文本/思考字段，未保留原生 `tool_calls` | 不走该方法；覆盖 `_chat_stream`，发送一次 `stream:false` 原生请求，转换全部工具调用后一次 yield |
| `qwen_agent/agents/assistant.py` | 默认可能经 Memory 获取文件知识 | `_RestrictedAssistant` 明确旁路知识注入；构造前设置无文件 memory 标记，避免创建默认 Memory |
| `qwen_agent/agents/fncall_agent.py` | 使用 `function_map` 调度工具并把真实结果回灌 | 保留官方循环；调用前后增加预算和审计钩子 |

适配没有改 `.venv/site-packages`、没有模拟工具返回、没有替换为自编 Agent 推理循环。传输采取非流式，是为了完整保存原始返回字段和服务端 usage；向框架仍提供其要求的迭代接口。返回 `tool_calls` 缺少 ID、非字符串参数或未知结构时失败，不自动猜测工具名或补造调用 ID。

已安装源码哈希见 `runs/local-agent/setup/framework-source-sha256.txt`。其中 `llm/base.py` 的 SHA-256 为 `2cbf81cf2f9035c2d6013f11f7ceff8dc141eb9329fcd8ba1617eeb59cd6d7ae`；`llm/oai.py` 为 `a342a8717d9ca775971b052b9b20ab465ba8d27122d95fb84f268cbf2b81ea2e`。框架升级后必须重新审查适配点和握手结果。

## 3. 调用契约、预算与隔离责任

```python
client = LocalAgentClient(
    tools=[read_code_tool, inspect_tool, patch_tool],  # 可信上层创建的 BaseTool 实例
    system_message=bounded_task_instruction,
    log_dir=run_directory / "model",
    max_model_calls=12,
    request_timeout_s=120,
    task_budget_s=900,
    max_output_tokens=2048,
    seed=0,
)
result = client.run([{"role": "user", "content": explicit_task_text}])
```

`result` 包含 `status`（`COMPLETED`、`STOPPED_LIMIT`、`ERROR`）、可 JSON 序列化的 `messages`、`model_calls`、`usage`、`elapsed_s`、`error`。`COMPLETED` 仅表示调度结束并收到最终回答，**不是修复 PASS**。同一 client 仅能运行一个任务；不能重复 `run()` 重置预算。

- 默认最多 12 次实际模型请求，单请求等待上限 120 秒，任务预算 900 秒。请求错误不自动重试；第 13 次不会发出。上层仍需对工具执行和整个进程设置硬截止，客户端不能中断任意阻塞工具。
- `temperature=0.2`、`top_p=0.8`，默认 `seed=0`，允许调用方明确指定 0–2³¹−1 的整数 seed；无反馈三个候选可按协议预先指定 1、2、3。默认输出上限 2048 token。这是实验配置，不宣称确定性或效果最优。`max_output_tokens` 可设置 1–8192；无反馈对照允许每候选 8192，3 次候选与 12×2048 的**最大生成预算**均为 24576，不等于实际 token 消耗匹配。
- `num_ctx=16384` 仍由 Ollama 服务环境固定，不往兼容 API 塞入该字段；Qwen-Agent 的粗略静默截断继续禁用。输入预算采用下述两种明确记录的方法，保留全部消息。超限返回 `STOPPED_LIMIT`，不自动扩大上下文或丢弃历史。
- 工具仅来自给定实例的唯一名称集合；未知工具返回拒绝信息。字段类型、额外字段、精确路径、只读快照和最多 3 次 patch，均由上层 `StrictTool`/handler 在副作用前验证。提示词中的“禁止”不能代替程序检查。
- 客户端只收纯文本消息，拒绝文件/图像内容项；不读取任务目录、隐藏测试文件、仓库知识库或系统环境密钥。工具能读什么取决于上层权限，不由模型传入路径自由决定。官方默认 Memory/RAG 被明确关闭。
- HTTP 忽略机器代理变量、拒绝重定向、无云端 fallback。真正的外网阻断由 root 启动的 loopback-only 网络 namespace 提供；客户端地址固定本身不构成完整网络沙箱。候选代码应在另一层隔离中执行，不能读取日志、协议或隐藏断言。

等待超时后 client 封存，不再调度工具或新模型请求。后台 HTTP 线程可能晚到，服务端生成是否停止未知；不能声称关闭连接即杀死推理。上层须终止任务进程并确认模型空闲或重置服务，再开始下一任务。文件日志目录不能复用，以免覆盖已有证据。

### 输入预算修订：仅复用已测的精确前缀

首轮记录 `experiments/local-agent-pilot/records/20260929t074300z-offline-01/` 完整保留。只读核对 p01/C-agent 的第 6 次实际请求，其完整请求体为 12,722 UTF-8 字节，服务端报告 `prompt_tokens=3057`；下一次拟发请求为 16,413 字节，被旧的 13,824 字节门槛拒绝。这说明“完整 JSON 字节数”在该轨迹中明显高于模型输入 token 数；不据此修改提示、隐藏断言、输出预算、12 次请求上限或 3 次补丁限制。

修订后的**工程保守输入上界**有两种计算方式：

1. **首次或不满足复用条件：`UTF8_WIRE_BYTES`。** `B = 完整请求体 UTF-8 JSON 字节数`。准入要求 `B + 输出预算 + 512 ≤ 16384`，因此首次门槛仍为 C/B 13,824 字节、D 7,680 字节。
2. **精确前缀复用：`MEASURED_PREFIX_PLUS_UTF8_SUFFIX`。** 只在当前 client 的紧邻上一成功实际请求具有有效正整数 `usage.prompt_tokens`、且通过当时的反查后启用。当前 `messages` 必须逐项包含上一请求的完整 JSON 结构前缀；不能改写最后一条旧消息、缩短、删掉或重排历史。除 `messages` 外的全部请求字段也必须完全相同，包括 `model`、`tools`、`seed`、输出上限和生成配置。比较忽略字典键顺序，但区分 `false` 与 `0` 等 JSON 类型。

复用时，设 `P` 为上一实际请求的 `prompt_tokens`，`S` 为新增消息列表完整 JSON 序列化后的 UTF-8 字节数，`N` 为新增消息条数：

```text
输入估计上界 B = P + S + 512 × N
上下文预算上界 = B + max_output_tokens + 512
准入条件：上下文预算上界 ≤ 16384
另要求完整请求体 ≤ 262144 字节
```

每条新增消息的 512 预留和全局 512 预留明确计入记录，用于覆盖消息与聊天模板边界变化。它们是针对冻结模型/模板采用的保守工程余量，**不是对任意 tokenizer、任意模板的数学上界证明**；不能把 `S` 或 `B` 报成服务端实际 token 数。没有复用时，上一计数、suffix 字节数等字段为 `null`，并记录回退原因。计数为零、布尔值、字符串或缺失时不复用；最新响应缺少有效计数后，也不跳回更早请求。测量不跨 client、任务或 run 保存复用。

每次服务返回后，先检查实际 `prompt_tokens` 是否超过已记录的 `B` 或允许输入预算，再把响应交给 Agent。若超过，记录 `input_budget_violation`，保留真实响应和 usage，但丢弃其可执行工具请求、封存 client，并以 `ERROR` 结束，交由上层停止本轮任务。服务端拒绝上下文或发生 HTTP 错误也沿错误路径停止，不重试、不提高 16K。响应缺少有效计数时记录不可得，下一次退回完整字节门槛。

该修订只让后续请求使用已有服务端测量值控制预算；不会选择“有利的历史回答”，不会把未发送的请求补记成模型调用，也不会改写首轮停止结果。新行为须在新的冻结版本和记录目录运行。

## 4. 日志与验证状态

每次请求保存 `model-XX-request.json` 和成功返回的 `model-XX-response.json`，保留实际 wire messages、原生 function calls、工具参数与返回字段；这些是 JSON 内容原样保留，非 HTTP 字节抓包。另存 `model-XX-input-budget.json`，记录预算方法、复用的 call ID/实际前缀 token 数、suffix JSON 字节数、新增消息数、两类 framing 预留、输入上界、上下文上界和固定 16K 限额。`events.jsonl` 的 `input_budget_checked`、`model_request`、`model_response` 将发送前预算和返回后的实际 `prompt_tokens` 关联；拒绝与反查违规另记。日志还包括工具调度、耗时和异常，`result.json` 保存最终任务状态。原始数据只限合成实验；私有执行日志不得公开，发布前仍需检查公开记录中不存在原始运行时凭据。

只有服务返回的 `usage` 才记为 `REPORTED_BY_SERVER`，缺失时为 `UNAVAILABLE`/`null`，不采用框架某些便捷接口生成的零 token 占位值，不用字符数充当实际 token。每次模型调用独立计时；工具耗时另记。超时或传输错误的 token 消耗不可得，必须单列。

本次预算修订的 18 项纯测试通过，覆盖原有调用 ID/序列化边界、seed 范围，以及精确前缀、前缀变化、tools/配置变化、无效计数、UTF-8 suffix 与 framing 计算、输入和完整请求体限制、服务端计数超过上界等。这些测试使用明确标注的算术输入，**没有 mock 模型成功，也没有发送任何模型请求**。

另只读复算首轮六个 C 的 29 组已保存真实请求/响应：23 个后续请求满足新算法的精确前缀条件，所有已观察 `prompt_tokens` 均未超过新估计上界。例如 p01 第 6 次的实际值 3057，对应新上界 4787。这是对既有记录的预算核对，不是新推理，不证明首轮被拒绝的下一次请求能够完成，也不改变旧轮 `STOPPED_LIMIT`。新预算下的真实连续调用与修复结果应以后续新 run 的原始记录为准；握手或预算校验本身不等于凭据修复能力证明。

## 官方来源

以下均于 2026-09-29 核查：

1. [Qwen-Agent 官方仓库与安装说明](https://github.com/QwenLM/Qwen-Agent)：最小安装、Assistant、自定义 BaseTool、原生 API 模式。
2. [PyPI qwen-agent 0.0.34](https://pypi.org/project/qwen-agent/0.0.34/)：实际安装版本；以本地 pip report 保存的 wheel URL/hash 为重现依据。
3. [官方 llm/base.py 源码导航](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/base.py)、[llm/oai.py](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/oai.py)：当前公开实现；本文行为核对另外绑定已安装 wheel 的哈希。
4. [官方 Assistant](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/agents/assistant.py)、[FnCallAgent](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/agents/fncall_agent.py)：知识路径及调度循环。
5. [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)：本地 `/v1/chat/completions` 与兼容接口边界。
6. [PyPA 安装 pip](https://pip.pypa.io/en/stable/installation/)：隔离环境的引导入口。
