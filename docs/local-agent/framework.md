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
)
result = client.run([{"role": "user", "content": explicit_task_text}])
```

`result` 包含 `status`（`COMPLETED`、`STOPPED_LIMIT`、`ERROR`）、可 JSON 序列化的 `messages`、`model_calls`、`usage`、`elapsed_s`、`error`。`COMPLETED` 仅表示调度结束并收到最终回答，**不是修复 PASS**。同一 client 仅能运行一个任务；不能重复 `run()` 重置预算。

- 默认最多 12 次实际模型请求，单请求等待上限 120 秒，任务预算 900 秒。请求错误不自动重试；第 13 次不会发出。上层仍需对工具执行和整个进程设置硬截止，客户端不能中断任意阻塞工具。
- `temperature=0.2`、`top_p=0.8`、`seed=0`，默认输出上限 2048 token。这是实验配置，不宣称确定性或效果最优。`max_output_tokens` 可设置 1–8192；无反馈对照允许每候选 8192，3 次候选与 12×2048 的**最大生成预算**均为 24576，不等于实际 token 消耗匹配。
- `num_ctx=16384` 由 Ollama 服务环境设置，不往兼容 API 塞入该字段。禁用 Qwen-Agent 的粗略静默截断，同时把完整 UTF-8 请求体限制为 `16384 - max_output_tokens - 512` 字节：默认 13824，8192 输出时为 7680。该限制是保守字节门槛，不是实际模型 tokenizer 测得的 token 数；上下文与模板仍须由服务配置和实际握手核对。超限返回 `STOPPED_LIMIT`，不自动扩大上下文或丢弃历史。
- 工具仅来自给定实例的唯一名称集合；未知工具返回拒绝信息。字段类型、额外字段、精确路径、只读快照和最多 3 次 patch，均由上层 `StrictTool`/handler 在副作用前验证。提示词中的“禁止”不能代替程序检查。
- 客户端只收纯文本消息，拒绝文件/图像内容项；不读取任务目录、隐藏测试文件、仓库知识库或系统环境密钥。工具能读什么取决于上层权限，不由模型传入路径自由决定。官方默认 Memory/RAG 被明确关闭。
- HTTP 忽略机器代理变量、拒绝重定向、无云端 fallback。真正的外网阻断由 root 启动的 loopback-only 网络 namespace 提供；客户端地址固定本身不构成完整网络沙箱。候选代码应在另一层隔离中执行，不能读取日志、协议或隐藏断言。

等待超时后 client 封存，不再调度工具或新模型请求。后台 HTTP 线程可能晚到，服务端生成是否停止未知；不能声称关闭连接即杀死推理。上层须终止任务进程并确认模型空闲或重置服务，再开始下一任务。文件日志目录不能复用，以免覆盖已有证据。

## 4. 日志与验证状态

每次请求保存 `model-XX-request.json` 和成功返回的 `model-XX-response.json`，保留实际 wire messages、原生 function calls、工具参数与返回字段；这些是 JSON 内容原样保留，非 HTTP 字节抓包。`events.jsonl` 逐项记录请求、响应、工具调度、耗时、异常和预算退出；`result.json` 保存最终任务状态。全部仅限合成实验数据，原始日志默认放 ignored `runs/`，不得把真实凭据放入公开包。

只有服务返回的 `usage` 才记为 `REPORTED_BY_SERVER`，缺失时为 `UNAVAILABLE`/`null`，不采用框架某些便捷接口生成的零 token 占位值，不用字符数充当实际 token。每次模型调用独立计时；工具耗时另记。超时或传输错误的 token 消耗不可得，必须单列。

截至本文件初次写入，真实验证包括：WSL 环境 `pip check` 通过；客户端语法检查通过；8 项纯序列化及请求前字节门槛测试通过。测试覆盖调用 ID 往返、并行调用 ID、普通无工具 JSON 文本、缺失 ID 拒绝、多完成拒绝、文件内容拒绝、文本伪造工具调用不触发、超限请求在发出前拒绝。它们**没有使用 mock 服务，也不证明模型连接成功**。

WSL 主网络空间的 `127.0.0.1:11435/api/version` 只读探测曾返回连接拒绝；正式服务由 root 在独立 namespace 启动，该结果不代表 namespace 内服务失败。实际兼容性必须由 `agent_pilot/handshake.py` 的运行时随机 nonce 两步工具测试确认：先调用工具获取随机值，再用真实结果调用第二工具验算，并保存原始请求/响应、工具审计和服务版本。本文不预写该测试结论，也不把握手成功扩大为修复能力证据。

## 官方来源

以下均于 2026-09-29 核查：

1. [Qwen-Agent 官方仓库与安装说明](https://github.com/QwenLM/Qwen-Agent)：最小安装、Assistant、自定义 BaseTool、原生 API 模式。
2. [PyPI qwen-agent 0.0.34](https://pypi.org/project/qwen-agent/0.0.34/)：实际安装版本；以本地 pip report 保存的 wheel URL/hash 为重现依据。
3. [官方 llm/base.py 源码导航](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/base.py)、[llm/oai.py](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/llm/oai.py)：当前公开实现；本文行为核对另外绑定已安装 wheel 的哈希。
4. [官方 Assistant](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/agents/assistant.py)、[FnCallAgent](https://github.com/QwenLM/Qwen-Agent/blob/main/qwen_agent/agents/fncall_agent.py)：知识路径及调度循环。
5. [Ollama OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)：本地 `/v1/chat/completions` 与兼容接口边界。
6. [PyPA 安装 pip](https://pip.pypa.io/en/stable/installation/)：隔离环境的引导入口。
