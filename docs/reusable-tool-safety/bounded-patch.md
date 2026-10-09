# bounded_patch：受控候选生成策略

该策略独立于保留的 Qwen-Agent 工具循环。程序取得授权对象证据及入口/必要测试，模型每轮只生成完整入口源码或明确 STOP；宿主执行器校验当前对象、修改权限和大小，应用到专用副本，并调用原 `check_project` 自动验收。模型 reason 没有判决权。

```powershell
.venv\Scripts\python.exe -m credproof_safety repair --strategy bounded_patch --config examples/material_assistant/credproof.toml --output <new-directory>/result.json
```

`--strategy qwen_agent` 仍保留原循环，默认不暗中改变。未知策略拒绝。不得在同目录反复运行覆盖记录。

## 接口与边界

- `agent_pilot/bounded_patch.py:build_payload/parse_response/BoundedPatchClient`：直接发送本地 `/api/chat`，`format` 为 JSON Schema，没有 tools 字段，没有旧工具 system/history。
- `credproof_safety/agent.py:_bounded_model_script/_bounded_initial_context`：复用已有只挂载白名单和私有网络模型启动器；新增模块只读挂载。程序 RPC 使用旧授权/材料校验及自动验收，不是模型工具调用。
- 支持输出仅 PATCH（完整 code）或 STOP（code=null）。严格字段、类型、大小、重复键、截断及工具调用检查；无 eval/exec 数据解析，无任意 Shell，没有云端回退。
- 每次重新提供当前代码正文、必要测试、全部原规则/场景、对应对象的真实反例和生成余额。不提供人工 fixed、参考补丁或隐藏答案。
- 上限：3次生成、1次格式纠正，总请求最多4；3候选/3验收；单请求120秒、任务900秒；16,384上下文、2,048输出及512安全预留，输入上界13,824。预算不足保留待发payload并阻断，不截断代码或放松要求。

官方接口核查：[Chat](https://docs.ollama.com/api/chat)、[Structured Outputs](https://docs.ollama.com/capabilities/structured-outputs)。文档说明 schema 为格式约束；本地实际服务版本和实际响应另保存，格式通过不代表安全通过。

## 本轮验证分类

`scripts/preflight-bounded-patch.py` 使用现有原件/v8失败/v7第二候选材料构造生产 payload，以及一次格式纠正协议分支。只验证输入保真与预算，不调用模型、不运行候选。`agent_pilot/tests/test_bounded_patch.py` 测试 JSON 接口和策略连接；源码级验收连线检查不是动态安全证明。

`scripts/run-bounded-patch-task.py` 先冻结源码/输入/规则/预算，再仅执行一次登记 p01 任务。原工具循环、v8失败和新策略不拼接统计。真实结果、所有候选及逐次验收在本轮固定证据入口追加；没有 PASS 就不制作成功 bundle 或启动交接。
