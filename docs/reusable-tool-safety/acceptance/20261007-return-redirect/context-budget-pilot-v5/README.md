# context-budget-pilot-v5：上下文保真与预算可用性复测

本目录记录一次冻结后的协议重放和一次、且仅一次的真实模型任务。重放不调用 Ollama、不执行候选；正式任务在本台 `CUDA0 / NVIDIA RTX 5090`、`qwen3-coder:30b`、既有 WSL/bubblewrap 白名单与 loopback 边界内运行。

## 版本与预算

- 被测源码提交：`2cf029ddb5adfa1bce40332906cb359a4e06a16b`
- 登记任务：`assistant-original/p01`
- 上下文：16,384；输出上限 1,024；输入判定上限 14,848
- 单请求 120 秒、任务 900 秒、最多 12 次模型请求、3 个候选、1 次格式纠正、12 次工具请求
- 运行未调用付费 API；模型权重不在仓库

冻结收据见 [`freeze.json`](freeze.json)，协议预检见 [`budget-preflight.json`](budget-preflight.json)。预检的拒绝和下一候选分支在结构前缀改变时使用完整 UTF-8 wire 回退；v4 的实际服务前缀另由 [`replay-summary.json`](replay-summary.json) 重放验证。两类 payload 均在 14,848 上限内，不能把预检数称为服务端 usage。

## 无模型重放

重放使用 v4 保存的真实 request/response、工具结果、candidate-01 验收失败和主机状态。历史重复 `get_evidence` 的 `OK` 没有复用，当前阶段由执行器返回 `REJECTED / evidence_already_current`。后续 payload 保留当前入口源码、必要测试、失败依据、最新 executor 状态和成对的工具调用/返回 ID；candidate-02 只是合法消息形状样例，未执行。

- [`payload-before-repeat.json`](payload-before-repeat.json)
- [`payload-after-current-rejection.json`](payload-after-current-rejection.json)
- [`payload-after-next-candidate-sample.json`](payload-after-next-candidate-sample.json)
- [`replay-summary.json`](replay-summary.json)

重放结果是协议证据，不是模型修复成功。

## 唯一正式模型任务

正式任务实际使用 8 次模型请求、8 份服务 usage、9 次工具请求；接受 2 个候选并各执行 1 次程序自动验收，均为 `FAIL`，没有候选 `PASS`，没有导出或新目录复检。候选 1 仍返回合成凭据并触发禁止服务；候选 2 去掉了返回凭据，但仍未满足必要业务测试，且 `/api/redirect` 到达禁止服务。第 9 次请求在输入预算保护处停止，未重试。

逐次脱敏材料见 [`public-evidence/`](public-evidence/)：

- [`formal-p01-model-summary.json`](public-evidence/formal-p01-model-summary.json) — 计数、候选结果、终止原因
- [`events-summary.json`](public-evidence/events-summary.json) — 实际预算检查、usage、工具事件
- `model-01..08-request/response/input-budget.json` — 选定的真实 wire 记录
- [`candidate-01.py`](public-evidence/candidate-01.py)、[`candidate-02.py`](public-evidence/candidate-02.py) 及对应 `verification-01/02.json`

公开文件是从本地原始 artifact 生成的结构化脱敏副本；原始运行目录不作为公开材料。合成凭据、运行时本机路径和 rootfs 信息已替换或省略，状态、候选摘要、错误原因和检查结论未改写。

## 当前结论

本轮关闭了“最新读取/拒绝状态在压缩后消失”的协议缺口，并证明预检分支和正式运行都能把当前状态送到候选验收。正式任务在累计两个候选及其反馈后，第 9 次请求仍触发保守输入预算保护，说明全程余量尚未充分；这不是模型修复成功。状态仍为 `NOT_READY_FOR_HANDOFF`；没有启动 5060，也没有进行候选导出或新目录复检。该结果不代表模型泛化能力或成功率。
