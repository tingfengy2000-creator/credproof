# 来源、复用与 AI 参与说明（准备稿）

核对日期：2026-09-29；任务起点 `711ad35`。用于准备创意作品赛报告中的来源和贡献说明，不替代许可审查、原创声明或组委会解释。赛事边界见 [competition-boundary.md](competition-boundary.md)。

## 组件与贡献分界

| 类型 | 实际使用与上游来源 | 本项目工作及证据 | 不应作出的表述 |
| --- | --- | --- | --- |
| 公开模型 | Ollama 分发的 [`qwen3-coder:30b`](https://ollama.com/library/qwen3-coder:30b)，30.5B、Q4_K_M；未做本项目训练或微调 | 固定模型工件、本地加载、受控任务与真实调用记录；`validation/model-manifest.json`、`model-config.json` | 自研基础模型、训练获得模型能力；不能把上游宣传能力当成本项目实测性能 |
| Agent 框架 | 官方 [Qwen-Agent](https://github.com/QwenLM/Qwen-Agent) `0.0.34`；使用上游 Assistant/FnCallAgent 原生工具循环 | 本地模型接口适配、受限工具集合、调用与 token 预算、证据记录；`framework.md`、`agent_pilot/model_client.py`、`tools.py` | 自研整套 Agent 框架；不能把安装了上游依赖等同于实际调用云服务 |
| 推理与隔离基础设施 | Ollama `0.34.4`、Python、WSL/Linux、bubblewrap、命名空间及 seccomp 等既有软件和操作系统能力 | 项目编写隔离封装、输入限制、边界探针与回执；`validation/ollama-installation.json`、`agent_pilot/isolation.py`、`sandbox_runner.py` | 自研操作系统沙箱；宿主隔离通过不等于 Python 同进程裁判可抵抗任意恶意内省 |
| 旧阶段模块 | 此工作树继承 CredProof 验证 CLI、Gitleaks 接入、此前 pilot 与文稿 | 保留阶段演进与历史结果；`credproof/`、`docs/preliminary/` | 当前 `agent_pilot/experiment.py` 未以旧扫描器作为 Agent 诊断引擎，旧结果不能算作本轮成绩；原工作区未提交前端/留出评测也不能算本分支交付 |
| 本轮新增实现 | `agent_pilot/` 的工具协议、受控执行裁判、固定规则基线、实验组织、过程汇总及案例 | 源码、冻结协议、逐步工具轨迹、候选补丁、测试和审计记录；新增部分与上游组件共同构成原型 | 有限且开发可见的合成案例不叫独立盲测；正常误报、预算耗尽和没有失败补丁迭代的事实不得省略 |
| 开发辅助 AI | **ChatGPT/Codex 参与方案比较、架构设计、主要代码生成与修改、调试、试验脚本及执行组织、结果核对、审计和文稿准备** | 会话决策、提交差异、命令记录与保存的实验产物；应由团队核实最终贡献说明 | 不能仅写“用于语言润色”，也不能直接声称全部由学生独立手工开发 |

底模、框架、工具补丁和开发辅助 AI 是不同层次：正式实验在本地运行 Qwen，不代表开发过程中未使用 ChatGPT/Codex；模型在试验中生成的补丁是**被评测产物**，不是上游模型或框架的原创证明。案例和裁判也有 AI 辅助构建，不能宣称其由与开发无关的独立人工盲审团队制作。

## 可追溯工件

- 模型层摘要：`sha256:1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a`，大小 18,556,688,736 字节；模型配置与许可层摘要保存在 `docs/local-agent/validation/model-manifest.json`。
- Qwen-Agent wheel `0.0.34` 的 SHA-256：`195264f9c1880f60f23781805d69bb3ffadfe944b7b70358f7115a0dd4bc59b7`；其他依赖来源见 `validation/dependency-sources.json` 与锁定清单。
- Ollama 二进制/归档摘要及官方下载地址见 `validation/ollama-installation.json`；实测源版本核对见 `validation/source-version-check.json`。保留原始记录，文稿不把后续修改追溯成已测版本。

Qwen-Agent 上游仓库和上述模型分发页面标示 Apache 2.0；最终分发前仍需逐项核对**实际工件**的 LICENSE/NOTICE、依赖许可、引用与再分发要求。现有摘要清单不是完成全部许可合规的证明，不默认将模型权重打进参赛包。

## 参赛前由团队补齐

逐人记录实际完成并能够解释的工作，例如需求判断、方案选择、源码审查、案例核验、实验批准与结果解释、报告和答辩；不要预填工时、贡献百分比或不存在的人工验证。向导师/组委会如实确认上述 AI 参与程度是否允许，以及如何满足独立研究和原创声明要求。

可以据实介绍为：“基于公开模型、官方 Agent 框架和既有隔离基础设施，构建受限的诊断—复现—修复原型，并保存过程证据。ChatGPT/Codex 参与了主要实现与验证组织，队伍实际贡献另列。”这只是事实陈述草稿，**不能据此断言已符合赛事原创性规定**。
