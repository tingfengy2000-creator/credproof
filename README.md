# 密证 CredProof

**面向 AI 工具的凭据泄露验证与受控修复系统。** 本地模型提出诊断与候选补丁，程序依据当前对象上的真实泄露证据授权修改，再在既有隔离环境中检查凭据通道、认证与功能。界面分别展示模型判断、程序确认、候选验收和完整任务状态；导出材料可重新执行检查。

当前阅读和运行入口是 **[初赛候选说明](docs/preliminary-candidate/README.md)**，包含作品报告、机制图、三分钟讲稿、答辩问答、配置、启动方式和逐案例证据。候选版本为 `0.2.0-preliminary.1`，未据此认定参赛资格、完成原创声明或成为比赛终版。

在本代码树根目录，用普通 Python 启动明确标注的真实历史回放：

```powershell
python -m agent_pilot.launch --demo
```

打开 `http://127.0.0.1:8765/`。h01、h03、h07 均标为 **REPLAY**，不会因打开页面而调用模型。现场运行是单独操作，要求已准备的本地模型和可信隔离设施；材料复检需要隔离设施，但不需要 GPU 或模型。只读环境检查使用 `python -m agent_pilot.preflight`，配置和首次准备边界见候选说明。

本轮文稿统一引用同一冻结批次的八个合成案例，不把后续已知案例复测拼入成绩。模型可能误判，固定流程也能解决多项案例；本作品不宣称通用漏洞修复、任意项目支持或 Agent 全面领先。

## 历史阶段入口

以下保留原阶段的实现、失败和评审口径，其启动命令、固定机器路径和阶段状态以当时版本为准：

- [原始验收器研发评审 0.1.0-review.1](docs/review/README.md)
- [本地 Agent 首轮评审](docs/local-agent/reliability/README.md)
- [本地 Agent 工具调用协议修订评审](docs/local-agent/tool-call-revision/README.md)
- [早期初赛定位](docs/preliminary/00_positioning_and_plan.md)与 [V2 方案原型](docs/plan-v2/README.md)

开源基础、实际 AI 参与和资格待确认项见 [来源披露](docs/local-agent/reliability/source-attribution.md)及 [候选模板核查](docs/preliminary-candidate/template-requirements.md)。模型权重、真实凭据和本机运行设施不随源码包提供。
