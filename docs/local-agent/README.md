# CredProof 本地 Agent 小试验

**2026-09-29 当前入口：[可靠性修正、真实单页与复检材料](reliability/README.md)。** 本文下方保留前两轮试验说明；其“尚未整合/误修改”等状态属于当时版本，不替代新一轮逐例结果。原版、旧失败与旧文档均保留。

这是独立的 `experiment/local-agent-pilot` 本地试验，不是比赛终版，不替换已发布 `v0.1.0-review.1`，本轮不推送或发布。实际原目录为 `E:\比赛\密证_CredProof`；试验 worktree 为 `E:\比赛\密证_CredProof-local-agent`，起点 `38456bad7d757d2e188e552372ae9bf1227773b6`。原 review.2 的未提交源码、界面和结果仍保留在原目录。

本轮问题是：本地模型是否会真实使用受限工具，在运行时证据的帮助下修好小型 Python 工具的凭据泄露，以及相对合理固定流程、一次性修复和无反馈多候选是否有实际增量。接通模型与修复成立分开验收。

**先读 [实际结果与限制](results.md)。** 两轮真实离线实验已完成并分别保留：本地 Qwen3-Coder 完成多步调用，四类泄露补丁全部通过；第二轮三例漏洞任务及一例正常任务符合记录中的完整流程。仍有一次预算耗尽和一个正常误报、无谓修改。A/B/C 产物结果相同，不能宣称 Agent 修复更强；本轮不再调优重跑追求全绿，不代表外部人工验收或决定全面转向。

## 读什么

- [预先协议](../../agent_pilot/protocol.json)：6 例、标签依据、13 条功能/异常/泄露条件、预算与分母。
- [可信需求](../../agent_pilot/fixtures/requirements.md)：仅本地模拟认证调用可以携带凭据；返回、日志、stdout/stderr 不可以。
- [裁判](../../agent_pilot/judge.py)：独立公式、精确凭据匹配、脱敏和覆盖检查，不依据案例 ID 给判决。
- [固定规则](../../agent_pilot/fixed.py)：通用 AST 修复，不含按案例编号选择答案。
- [模型客户端](../../agent_pilot/model_client.py)、[权限工具](../../agent_pilot/tools.py)、[真实比较控制器](../../agent_pilot/experiment.py)。
- [框架与依赖来源](framework.md)、[隔离边界与探针](isolation.md)。
- [两步真实握手](../../agent_pilot/handshake.py)、[离线监督进程](../../agent_pilot/offline_run.py)。
- [预先过程评分规则](process-scoring.md)：把模型主动复现、反馈确实进入下一轮与最终补丁通过分开，不能用最终 PASS 替代闭环证据。

目前源码不包含模型权重。权重和软件位于仓库外 `/home/tingfeng/credproof-agent-runtime` 及 `E:\CredProof-local-runtime`。模型运行配置与实测结论以各次不可覆盖的运行目录为准；准备阶段的测试不能替代实际推理。

当前已验证组合：Qwen-Agent 0.0.34、Ollama 0.34.4、`qwen3-coder:30b` GGUF Q4_K_M；完整模型 digest 和来源见 [验证元数据](validation/model-download.json)。只在本机 Windows + WSL Ubuntu 24.04 验证，未宣称其他系统部署通过。

## 运行边界

采用 Qwen-Agent `Assistant` 的官方工具循环，只有少量 Ollama 接口适配；不启用文件知识库、RAG、通用代码执行、MCP、云模型或 API Key。只读 `tool.py`、结构化触发、脱敏证据、最多三份补丁和固定复检是模型全部权限。源文本和工具结果均为不可信数据，不能改变权限。

候选不在 Windows 或 WSL 的普通主机进程中执行。独立 bubblewrap 建立最小只读根目录、进程/挂载/网络等命名空间，删除 capabilities，并使用 seccomp、地址空间/CPU/输出/临时文件/超时限制。原 E 盘、用户目录、GPU、模型和隐藏裁判均不挂给候选。隔离门禁先检查设施身份与完整边界探针；缺证据不能开启执行。

可信模型服务和控制器另外运行在只有 loopback、无外部路由的外层 network namespace。准备下载在联网阶段完成，正式运行不靠“localhost 配置”冒充离线：记录命名空间成员、网络接口、路由和实际外连失败。不会改宿主防火墙/代理，也不会中断 Codex 网络。

模拟认证是隔离内的内存对象方法，不是远程真实账户。候选仍与单次采集器共享 Python 进程；静态任务限制减少反射、导入和采集器访问，**不能把它描述成对任意恶意 Python 程序防篡改的可信裁判**。只验证固定合成工具和明确覆盖的完整明文凭据，不涵盖编码、拆分、计时等隐蔽通道。哈希固定材料身份，不是第三方认证。

## 本机命令

准备环境使用 WSL Ubuntu-24.04、系统 Python 3.12.3 和独立 venv。精确 Python 依赖见 [requirements-lock.txt](../../agent_pilot/requirements-lock.txt)。Ollama 使用官方 Linux 独立归档，本地解包，不注册系统服务；模型固定为 `qwen3-coder:30b`，官方 Q4_K_M，下载后必须核对完整 digest 才使用。

```powershell
# 在试验 worktree 中执行；没有任何 push/release 命令。
wsl -d Ubuntu-24.04 --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -m unittest agent_pilot.test_model_client -v
wsl -d Ubuntu-24.04 --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -m unittest discover -s agent_pilot/tests -v
wsl -d Ubuntu-24.04 --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -m agent_pilot.isolation prepare
wsl -d Ubuntu-24.04 --exec /home/tingfeng/credproof-agent-runtime/venv/bin/python -m agent_pilot.isolation probe

# 模型和隔离准备完成后：必须换一个全新的输出目录名。
wsl -d Ubuntu-24.04 --exec unshare --user --map-root-user --net --fork /home/tingfeng/credproof-agent-runtime/venv/bin/python -m agent_pilot.offline_run --output experiments/local-agent-pilot/records/new-offline-run
```

`prepare/probe` 只处理固定可信设施与自写探针；重新 prepare 会关闭旧执行门禁，必须重新 probe。主入口先真实随机挑战握手，再完整验证全部原始案例标签，最后比较 A/B/C 及预先指定的 p01/p03 无反馈多候选。每次新目录保留所有中间补丁、请求/响应、失败和理由；不挑最好一次冒充唯一结果。

本机环境已准备完成，不必再次下载或重新 prepare。首次准备的官方来源、依赖锁定、隔离构建与探针见 [framework.md](framework.md) 和 [isolation.md](isolation.md)；运行时路径按本机独立目录固定，不是通用安装器。模型下载与完整性校验使用 `agent_pilot/download-model.py`，Ollama 官方归档解包使用 `agent_pilot/prepare-ollama.py`；权重始终不入 Git。

默认上下文 16384，单任务最多12次模型请求、每次2048输出 token，最多3补丁；每请求120秒、任务900秒。无反馈三候选每次上限8192，最大生成预算合计同为24576，实际调用数、输入/输出 token 和耗时仍不相等，必须按实测报告。固定规则不使用模型。所有 ERROR/超时停止后续推理，监督进程停止自己启动的模型服务；不自动换模型或付费回退。

## 如何看证据

`experiments/local-agent-pilot/records/<run>/` 为保留的脱敏记录：协议/源码 hash、真实模型请求与返回、工具轨迹、全部候选、逐例判决、资源与离线检查。`runs/local-agent-private/` 为隔离采集器的原始合成凭据记录，模型工具不可读取、默认不纳入 Git。可公开记录须检查没有完整 `CP_EXEC_` 运行时值。

PASS 指完整固定条件通过；明确行为/泄露/允许范围反例为 FAIL；执行条件或证据不足为 UNKNOWN。模型文本中的 PASS 不参与判决，框架 COMPLETED 也不等于修复 PASS。保存旧失败，修正后另开新记录，不能改写先前实验。

已有 [A-only 隔离预检](../../experiments/local-agent-pilot/records/20260929t063200z-fixed-preflight/results.json)：四个原始泄露和两个正常标签均先执行确认，固定规则修复 4/4，正常保持通过且未修改 2/2，模型调用为 0。正式推理前又明确“最终选择最后提交文件”的提示，并拒绝空白假设；没有改变样例、裁判或固定基线。后续汇总用 `python -m agent_pilot.summarize --records <完整比较目录> --output <新目录>`，人工核查假设与反馈作用，不能自动宣称模型推理质量。

费用口径仅为“作品本次运行未调用付费 API”；硬件、电力和开发工具订阅不是零成本。本试验由同一开发过程构造，不是独立盲测，六例结果不能说明稳定成功率或优于现有工具。
