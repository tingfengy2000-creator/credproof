# context-budget-pilot-v4：最新读取保真与有限复测

本目录同时保存两类材料，不能混为模型成功：

- `replay-summary.json`、`payload-before.json`、`payload-after-read-05.json`、`payload-after-read-12.json`：使用 v3 原始请求、响应和主机工具结果做的**协议重放**，不调用模型、不执行候选。
- `public-evidence/`：一次在 5090、既有隔离边界内完成的**真实模型任务脱敏证据**，包含实际请求、响应、usage、工具轨迹、候选和程序自动验收结果。

## 本轮关闭的循环问题

修正前的 `model-05` 请求没有保留刚执行的入口读取；v3 的第 5—12 次请求因此具有相同的请求摘要。修正后，重放中的每个最新 `read_code` 调用都保留与返回的配对 ID、`tool.py` 正文、候选 1 的真实 `FAIL` 以及主机最新 `executor_state`。`tool_calls_used` 在快照中从 5 递增至 12，剩余额度同步递减，8 个 wire payload 的 SHA 不相同。非 OK 状态及 reason 没有被改写；重复的 `get_evidence` 在当前证据已存在时由执行器返回 `evidence_already_current`，而不是重新生成旧证据。

这证明了消息协议不再丢失“刚刚完成的读取”和状态；它不证明模型修复成功。协议重放的 `model_run` 明确为 `not_run`。

## 预算预检

`budget-preflight.json` 使用当前客户端序列化、工具 schema 和固定摘要计算四个阶段的保守输入上界：首请求、证据加两份源码、程序自动验收失败、失败后重新读取。最大上界为 `14583 / 14848`，`all_within_declared_budget=true`。这是协议预检，不是服务返回的 token 用量，不执行模型。

## 一次真实模型任务

任务为登记的 `assistant-original/p01`，模型 `qwen3-coder:30b`，源码/配置冻结在提交 `502072a1e20459bbf0e474ce0630c6cc22b6a842`。实际设备由 Ollama 日志确认是 `CUDA0 / NVIDIA GeForce RTX 5090`；边界探针确认白名单挂载、私有网络命名空间和无付费 API。

真实结果：5 次模型请求、5 份服务 usage、6 次工具请求、1 个被接受候选、1 次 `program_auto_verify`。候选 1 的 SHA 为 `3877266f231b1a5cfd2a1c6412a7ee0c5d11393635270a473c0a3142c3dccce8`，验收为 `FAIL`：凭据仍出现在返回值，且必要业务、文件和网络边界检查没有全部满足。模型随后再次请求已完成的 `get_evidence`，客户端保守预算保护停止任务；没有重试、没有导出，也没有新目录复检。该任务的状态是 `INCOMPLETE / STOPPED_LIMIT`，不是 PASS。

## 复核入口

- 协议结果：[`replay-summary.json`](replay-summary.json)
- 预算预检：[`budget-preflight.json`](budget-preflight.json)
- 真实任务汇总：[`public-evidence/run-summary.json`](public-evidence/run-summary.json)
- 实际脱敏请求：[`public-evidence/model-01-request.json`](public-evidence/model-01-request.json) 至 `model-05-request.json`
- 实际脱敏响应：对应的 `model-01-response.json` 至 `model-05-response.json`
- 结果与候选：[`public-evidence/formal-p01-model-result.redacted.json`](public-evidence/formal-p01-model-result.redacted.json)、[`public-evidence/candidate-01.py`](public-evidence/candidate-01.py)
- 边界与设备：[`public-evidence/boundary-probe.json`](public-evidence/boundary-probe.json)、[`public-evidence/service-boundary.json`](public-evidence/service-boundary.json)、[`public-evidence/runtime-device.json`](public-evidence/runtime-device.json)

原始模型权重、rootfs、虚拟环境和本机完整绝对路径未发布。完整本地原始轨迹保留在工作区，公开目录仅包含可复查所需的脱敏派生材料。

当前交接状态：`NOT_READY_FOR_HANDOFF`。阻断项是没有当前真实模型候选通过全部安全与业务验收，因此没有可供公开取件后复检的 PASS 候选。
