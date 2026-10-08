# context-budget-pilot-v6 公共证据

本目录是 `formal-p01-model-result.json` 的结构化脱敏派生材料，源码提交为 `f7ac7aa7a6342de8e240e8e10146dbebe64133fe`。它保留真实状态、计数、候选摘要、程序自动验收结果和未发送请求的预算信息；完整原始 artifact 仍留在本地评审目录，没有被这份派生材料覆盖。

- `formal-run-summary.json`：9 个已发送模型请求、9 份服务 usage、10 个已处理工具请求、2 个接受候选、2 次程序自动验收，均为 `FAIL`。第 10 个模型请求未发送，输入上界 16642 超过 14848，context 上界 18178 超过 16384。
- `tool-trace-summary.json`：逐工具状态、reason、候选与最新 executor state；`evidence_already_current`、`NO_CHANGE` 和 `candidate_already_verified` 保持原状态。
- `unsent-request-10-budget.json`：实际未发送请求的预算收据，不是服务 usage。
- `candidate-01.py`、`candidate-02.py`：本次模型实际提交并被程序接受进入自动验收的合成候选。
- `candidate-01-verification.json`、`candidate-02-verification.json`：对应程序自动验收的脱敏摘要。
- `targeted-regression.txt`：本轮定向回归的真实命令、退出码和结果（48 passed）。
- `model-request-summary.json` 与 `model-trace/`：9 次实际请求/响应、usage、工具调用名和请求摘要；请求/响应在脱敏检查后保持 JSON 语义；派生文件因换行规范化与原始字节不同，原始/派生 SHA-256 见 `derivation-receipt.json`。
- `unsent-request-10-payload.json` 与 `unsent-request-10-budget.json`：第 10 次完整未发送 payload 和预算收据，明确无服务 usage。
- `replay-reference.json`：无模型重放的输入、预期、输出和 13,788 字节预算来源。
- `delivery-receipt.json`、`derivation-receipt.json`：被测源码、两个交付提交及原始/派生文件 SHA-256 关系。
- `budget-breakdown.json`：第 9/10 次 wire 的实际分类、重复项和根因；第 10 次没有服务 usage。
- `duplicate-verify-dedup/`：用实际未发送 payload 重放当前精简响应，证明新 payload 预算通过且 FAIL 状态保留。

无模型协议重放沿用 v5 真实材料，详见 [`replay-summary`](../../context-budget-pilot-v5/no-change-dedup/replay-summary.json) 与 [`reconstructed-next-request`](../../context-budget-pilot-v5/no-change-dedup/reconstructed-next-request.json)。本轮没有候选通过全部安全与业务检查，因此没有同一候选导出或新目录复检；状态保持 `NOT_READY_FOR_HANDOFF`。
