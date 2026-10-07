# context-budget-pilot：受限模型任务记录

本目录记录 `assistant-original/p01` 在 2026-10-07 的一次冻结模型运行。它验证的是消息预算适配是否让任务能够继续进入“证据→读取→提交→验收”阶段；它没有取得合格修复，因此不能作为 Agent 修复成功案例。

## 冻结条件与预算预检

- 模型：本地 Ollama `qwen3-coder:30b`，不调用付费 API；模型权重不在仓库。
- 设备：本台 `CUDA0 / NVIDIA GeForce RTX 5090`。设备与白名单边界见 [`public-evidence/ollama-stderr.txt`](public-evidence/ollama-stderr.txt)、[`public-evidence/boundary-probe.json`](public-evidence/boundary-probe.json) 和 [`public-evidence/service-boundary.json`](public-evidence/service-boundary.json)。
- 预算：16,384 上下文、1,024 最大输出、最多 12 次模型请求、3 个候选、1 次格式纠正、单请求 120 秒、任务 900 秒。
- 冻结记录：[`run-freeze.json`](run-freeze.json)。协议预检：[`../20261007-context-budget-preflight.json`](../20261007-context-budget-preflight.json)。

预检使用实际客户端序列化和工具 schema，不发送模型请求。首请求摘要为 1,270 字节；证据加两份源码后的保守上界为 13,808 输入字节、15,344 上下文上界；候选失败反馈经历史压缩后为 8,512 输入字节、10,048 上下文上界；三个阶段均在声明限制内。这里的字节值是保守边界检查，不是服务返回的 token 用量，也没有用“字节除以 4”推算 token。

## 一次正式运行的真实结果

正式命令见 [`public-evidence/command-output.redacted.txt`](public-evidence/command-output.redacted.txt)。任务结果为 `INCOMPLETE`，模型停止原因是 `Model request budget exhausted`；没有发生 `input_budget_exceeded`，也不是第 2 次请求超时。

| 项目 | 实际记录 |
| --- | --- |
| 模型请求 / usage | 12 / 12 |
| 工具请求尝试 | 15 |
| 工具请求在执行器上限前接受 | 12 |
| 因上限拒绝 | 3 |
| 接受候选 | 2 |
| 候选 1 | 已验收，`FAIL`；保留在 [`verification/verification-01.json`](public-evidence/verification/verification-01.json) |
| 候选 2 | 已保存但未验收，`UNVERIFIED`；见 [`verification/candidate-02.py`](public-evidence/verification/candidate-02.py) |
| 可信 PASS | 0 |
| 导出 / 新目录无模型复检 | 未执行，不适用 |

候选 1 的失败是真实验收结果；候选 2 没有足够证据，不能标为 PASS 或 FAIL。完整但脱敏的模型请求、响应和事件可从 [`public-evidence/model-trace/`](public-evidence/model-trace/) 复查；[`public-evidence/run-summary.json`](public-evidence/run-summary.json) 是由这些记录派生的汇总。原始运行目录保留在本机，不提交含运行时合成值的原件。

## 本轮实现的预算适配

`credproof_safety/agent.py` 只向模型发送当前任务的入口、有限文件索引、修改范围、规则摘要和有界场景信息；完整报告仍单独保存。`get_evidence` 的反馈包含必要失败项、已执行/未执行场景、返回值泄露类型、关键观察和对象标识，并记录省略字段与数量。`agent_pilot/model_client.py` 在提交/验收阶段保留基础任务和最新依赖工具对，执行器仍保留完整历史，因此不会用重复日志扩大下一次请求。

对应回归：`agent_pilot/tests/test_model_boundary.py` 以及全套 `agent_pilot/tests`。本轮实际运行全套回归为 `110 passed, 1 warning`，预检退出码为 0；收据见 [`post-run-checks.json`](post-run-checks.json)。这些回归和预算预检没有调用模型，不能算模型修复结果。

## 当前结论

上下文预算问题已通过协议预检并在一次真实运行中不再复现；模型确实在 5090 上完成了 12 次请求并产生了两个候选，但没有可信修复 PASS。由于没有 PASS 候选，本轮没有导出或新目录复检。当前交接状态仍为 `NOT_READY_FOR_HANDOFF`，后续不能把候选 2 或旧历史结果拼成成功。
