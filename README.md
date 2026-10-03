# 密证 CredProof——面向 AI 工具的凭据泄露验证与受控修复系统

系统结合本地大模型补丁生成与程序控制的安全验收，针对凭据泄露问题给出候选修复，并检查泄露是否消除、必要业务行为是否保持，支持材料导出与复检。

当前版本 **`0.2.0-preliminary.5`**：从深色作品首页进入 h01、h03、h07 三个精选案例，依次查看问题、实际证据、补丁差异和复检结果。[初赛候选入口](docs/preliminary-candidate/README.md)集中提供作品说明书、摘要、机制图和启动方式；[一页展示顺序与录屏分镜](docs/preliminary-candidate/presentation-guide.md)可直接用于排练。

本版为材料与文案更新，未新增实验或修复能力。[价值主张](docs/preliminary-candidate/value-and-innovation.md)及[证据索引](docs/preliminary-candidate/evidence-index.md)解释为谁解决什么；[开发者体验包](docs/preliminary-candidate/experience-packet/README.md)待真人执行。

三个特点：**证据驱动的候选生成与反馈调整；程序控制的修改权限与安全/业务验收；对应修复对象的材料导出与复检。**

在本代码树根目录，用普通 Python 启动明确标注的真实历史回放（默认只读查看，不要求模型或 WSL）：

```powershell
python -m agent_pilot.launch --demo --mode view
```

打开 `http://127.0.0.1:8765/`。h01、h03、h07 均标为 **REPLAY**，不会因打开页面而调用模型。现场运行是单独操作，要求已准备的本地模型和可信隔离设施；材料复检需要隔离设施，但不需要 GPU 或模型。只读环境检查使用 `python -m agent_pilot.preflight`，配置和首次准备边界见候选说明。

本轮文稿统一引用同一冻结批次的八个合成案例，不把后续已知案例复测拼入成绩。模型可能误判，固定流程也能解决多项案例；本作品不宣称通用漏洞修复、任意项目支持或 Agent 全面领先。

前版接入 [Twine 历史配置泄露组件接入](docs/external-scenario/twine/README.md)、[三种启动入口](docs/preliminary-candidate/startup-modes.md)、[一页贡献与代码对应](docs/preliminary-candidate/contribution-map.md)、[真实演示视频](docs/preliminary-candidate/video/README.md)及 [源码讲解](docs/preliminary-candidate/source-walkthrough.md)。外部结果单列，原八例完整统计不变。

## 历史阶段入口

以下保留原阶段的实现、失败和评审口径，其启动命令、固定机器路径和阶段状态以当时版本为准：

- [原始验收器研发评审 0.1.0-review.1](docs/review/README.md)
- [本地 Agent 首轮评审](docs/local-agent/reliability/README.md)
- [本地 Agent 工具调用协议修订评审](docs/local-agent/tool-call-revision/README.md)
- [早期初赛定位](docs/preliminary/00_positioning_and_plan.md)与 [V2 方案原型](docs/plan-v2/README.md)

开源基础、实际 AI 参与和资格待确认项见 [来源披露](docs/local-agent/reliability/source-attribution.md)及 [候选模板核查](docs/preliminary-candidate/template-requirements.md)。模型权重、真实凭据和本机运行设施不随源码包提供。
