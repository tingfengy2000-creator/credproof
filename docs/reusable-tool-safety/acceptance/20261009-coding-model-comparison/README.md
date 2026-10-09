# 单次编码模型工程对照（dev33）

登记任务 assistant-original/p01；原始项目、组件 API、规则、必要业务测试及生成策略保持 dev32。仅新增固定 qwen2.5-coder:32b-instruct-q4_K_M，不覆盖 Qwen3 记录。本页暂为运行前登记，结果随后追加。

最多一次无项目代码结构化预检、一次正式任务；正式任务最多3次实质生成、1次格式纠正、4次请求、3候选/3程序验收。16K上下文、2048输出、512预留、120秒请求、900秒任务。持久化独占 claim 在宿主保留，重启/换目录不恢复额度。失败不追加第二轮。

[登记与限制](registration.json)。[固定模型配置](../../../../agent_pilot/model_config.py)、[生成客户端](../../../../agent_pilot/bounded_patch.py)、[原边界和自动验收](../../../../credproof_safety/agent.py)。

官方来源：[固定标签](https://ollama.com/library/qwen2.5-coder:32b-instruct-q4_K_M)、[结构化输出接口](https://docs.ollama.com/capabilities/structured-outputs)。模板由模型自己的 manifest 读取，无模板覆盖、付费 API 或自动回退。

状态：NOT_READY_FOR_HANDOFF。此页不是模型成功或外部验收声明。
