# context-budget-pilot-v7 公共证据

本目录是本轮唯一一次真实本地模型任务的结构化脱敏证据。模型为本地
`qwen3-coder:30b`，经 Qwen-Agent/Ollama 在 5090 主机的受控 bubblewrap
边界内运行；没有调用付费 API，也没有把模型权重、rootfs 或虚拟环境放入仓库。

本轮先完成了当前客户端的无模型续行预检（见
`../context-budget-pilot-v6/public-evidence/current-client-continuation/`），随后只登记并执行一次
`assistant-original/p01`。实际结果为：9 次模型请求、9 份服务 usage、10 次工具请求、2 份候选，
2 次由程序自动验收，候选均为 `FAIL`；任务因连续相同读取触发 `STOPPED_NO_PROGRESS`，没有模型
修复 `PASS`，没有导出或新目录复检。

- `formal-run-summary.json`：固定源码提交、模型、5090/边界、预算、计数、终态和交接状态。
- `model-request-summary.json`：9 次请求的服务 usage 摘要；不把未发送请求或本地估算当作 usage。
- `tool-trace-summary.json`：10 次工具请求及可信状态，保留两个候选的自动验收结果和拒绝原因。
- `candidate-01.py`、`candidate-02.py`：模型实际提交、被执行器接受的合成候选。
- `candidate-01-verification.json`、`candidate-02-verification.json`：逐候选的脱敏安全、业务和边界结果。
- `run-command.txt`：实际命令、退出码及“只运行一次”的说明。
- `evidence-manifest.json`：本目录公开文件的 SHA-256 清单。

候选 2 确实去除了正常返回和日志中的凭据，但仍让路径穿越读取到达执行路径，且跟随
`/api/redirect` 抵达禁止服务并携带认证头；pytest 为 3 通过、1 失败。因此这不是可交付修复。
`STOPPED_NO_PROGRESS` 只描述执行器在重复读取无新信息后的停止，不等于模型成功，也不等于
服务端超时。当前交接状态仍为 `NOT_READY_FOR_HANDOFF`；5060 尚未启动。

完整原始 artifact 仅保留在本地评审目录，以上文件是可公开复核的结构化派生件；脱敏和字段省略不
改变候选代码、状态、对象关系或失败原因。
