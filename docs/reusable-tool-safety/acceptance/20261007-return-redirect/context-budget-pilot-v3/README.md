# context-budget-pilot-v3

这是 `assistant-original/p01` 在本台 RTX 5090/CUDA0 受控边界中的一次有限正式复测。v2 原始失败记录保留在同级 `context-budget-pilot-v2/`，本页只描述 v3，不把两轮的最好结果拼接。

## 固定条件

- 模型：本地 Ollama `qwen3-coder:30b`；不调用付费 API。
- 边界：现有 bubblewrap 白名单、私有 loopback；合成凭据与模拟服务。
- 预算：最多 12 次模型请求、12 次工具请求、3 个有效候选、3 次程序验收、1 次格式纠正；单请求 120 秒、任务 900 秒、16,384 上下文、1,024 输出。
- 冻结：[`run-freeze.json`](run-freeze.json)。

## 真实结果

实际命令：

```powershell
.venv\Scripts\python.exe -m credproof_safety repair --config examples/material_assistant/credproof.toml --output context-budget-pilot-v3/formal-p01-model-result.json
```

结果为 `INCOMPLETE / STOPPED_TOOL_BUDGET`：12 次模型请求、12 次工具请求，接受 1 个候选，程序自动验收 1 次且为 `FAIL`；可信 PASS 为 0，未导出候选、未做新目录复检。第 12 个工具结果返回后执行器停止了后续模型请求。完整本地原件不入 Git；公开可读的结构化记录在 [`structured-redacted-v1/evidence.json`](structured-redacted-v1/evidence.json)。候选代码在 [`structured-redacted-v1/candidate-01.py`](structured-redacted-v1/candidate-01.py)。

## 读取证据

- 上下文压缩与状态保持协议测试：[`../../../../../../agent_pilot/tests/test_model_boundary.py`](../../../../../../agent_pilot/tests/test_model_boundary.py)。
- 可信验收完整脱敏结果：[`structured-redacted-v1/verification-01.redacted.json`](structured-redacted-v1/verification-01.redacted.json)。
- 模型逐次请求/响应的字节哈希、预算、usage 和原生工具名索引：[`structured-redacted-v1/model-trace-index.json`](structured-redacted-v1/model-trace-index.json)。
- 预检：[`../20261007-context-budget-preflight.json`](../20261007-context-budget-preflight.json)。
- v2 发现工具额度停止问题的原始记录：[`../context-budget-pilot-v2/`](../context-budget-pilot-v2/)。
- candidate-02 的独立事后核验：[`../context-budget-pilot/post-run-verification-candidate02-v1/public-evidence/post-run-verification-summary.json`](../context-budget-pilot/post-run-verification-candidate02-v1/public-evidence/post-run-verification-summary.json)。

`structured-redacted-v1` 使用结构化字段选择，保留候选源码和判定字段；未对嵌入 Python 代码做宽泛路径正则替换。模型权重、rootfs、虚拟环境、完整 mountinfo 和本机绝对路径没有发布。

## 当前门槛

这次运行证明了：当前候选上下文不会因压缩而丢掉已提交代码，工具拒绝不会被改成成功，接受候选会进入可信程序验收且工具额度耗尽会停止。它没有证明模型能完成该任务；仍为 `NOT_READY_FOR_HANDOFF`。

源码与证据收据提交：`a54dede`（后续仅追加公开入口收据，不改变本次模型结果）。
