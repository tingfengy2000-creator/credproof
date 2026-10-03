# 一页可核对的技术贡献

**密证 CredProof——面向 AI 工具的凭据泄露验证与受控修复系统。** 本项目把本地模型候选、程序实施的修改权限和对象对应材料串成可操作流程；增量是限定任务上的工程设计与实现，不把开源 Agent 接入、反馈循环、哈希或普通状态控制称为新算法。

| 自行实现内容 | 解决的问题与机制 | 代码位置与函数 | 案例依据 |
|---|---|---|---|
| 证据驱动的候选生成与反馈调整 | 固定程序先执行公开诊断；模型读取代码、选工具、生成候选，实际失败回执进入下一请求 | `agent_pilot/reliability.py`：`GovernedSession.initialize`、`run_method`；`model_client.py`：`LocalAgentClient.run` | h01 修好本项目固定启发式未覆盖的参数日志；h03 第一补丁仍保留真实值，第二补丁改变日志内容后通过 |
| 程序控制的修改权限与安全/业务验收 | 当前副本与禁止通道必须有确认泄露，才允许修改；检查业务行为及修改边界，执行器决定完成 | `reliability.py`：`authority`、`submit`、`check`；`judge.py`：`validate_source`、`judge_trial`；`isolation.py`：`run_isolated` | h07 原代码保留；外部 Twine 的前两份候选被预先固定边界拒绝，第三份通过 |
| 对应修复对象的材料导出与复检 | 导出检查当前对象与材料绑定；复检区分旧报告适用性、历史材料完整性和新结果 | `web.py`：`_material`、`_require_current_material`；`bundle.py`：`recheck_bundle`、`_historical_integrity` | 对象变化定向回归；h01/h03/h07 可移交材料；Twine 独立适配器 `external_twine.py`：`export`、`recheck` |

**清楚区分三个故事。** h01 仅支持相对本项目固定启发式的有限候选增量。h03 支持一次真实反馈调整；同例固定流程直接成功。Twine 是已知历史问题的窄组件接入，修复轮廓预先限制，不能用作普遍自主修复或领先证明。固定初始测试由程序提供，不全部归因于 Agent 自主发现。

**完整批次不改口径。** `20260929t095000z-holdout8` 的 A/B/C 问题例修复为 3/4、1/4、4/4；对象通过为 7/8、5/8、8/8；完整任务为 7/8、4/8、6/8。外部结果单列，不拼接成整体全通过。具体出处见 [说明书测试章节](manuscript.md)。

**来源归属。** Qwen3-Coder 是现成预训练模型；Qwen-Agent 提供 Assistant/工具循环；Ollama 提供本地推理；bubblewrap、Linux namespaces/seccomp 提供隔离基础。本项目负责受限工具、证据门槛、裁判、完成控制、对象绑定、材料复检、工作台及限定适配。Twine 原配置逻辑和许可证保留。ChatGPT/Codex 实质参与设计、主要代码、调试、测试组织及材料生成；成员贡献、AI 辅助参赛范围和原创声明由参赛者与导师/组委会确认，未代签、未提交。
