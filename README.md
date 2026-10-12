# 密证 CredProof——面向Python工具的AI辅助安全修复与证据验收工作台

当前主线：AI提出候选，程序独立验收，开发者修订并决定是否采纳。正式修订可保持PASS/PENDING；采纳不自动应用原仓库。

[本轮唯一评审入口](docs/reusable-tool-safety/acceptance/20261010-human-review/README.md) · 本轮运行时模型调用0，历史自动修复失败完整保留。

[5060前端研发交接入口](docs/handoff/frontend-5060/README.md)：冻结dev35人机协作基线，独立只读历史查看无需模型或隔离环境；真实验收、审批和导出复检仍仅在5090执行。交接状态以该入口收据为准，外部独立源码复核尚未完成。

[PR #1 路径摘要定向修复](docs/review/pr-1-tree-identity/README.md)：dev36 固定跨宿主排序，保留旧 Windows 对象摘要；原 dev35 安装包与 Linux 失败记录不改写。仅修对象身份计算，不恢复模型实验或改变安全判定。

## 历史主线与交付（保留原结论，不代表dev35当前状态）

历史dev34：[一次定点反馈修订与交付收尾](docs/reusable-tool-safety/acceptance/20261010-feedback-revision/README.md)。统一格式/语法入口已安装接通；唯一新模型请求产生1候选并自动验收FAIL，实际仅删import os，业务1通过3失败。原UNKNOWN及上轮FAIL不改写；**NOT_READY_FOR_HANDOFF**，本轮已结束，无追加生成或5060交接。

历史定向收尾：[已有输出格式归一化与一次事后验收](docs/reusable-tool-safety/acceptance/20261010-format-normalized/README.md)。仅去掉模型原有外层围栏，语法通过；原规则隔离检查 **FAIL**（业务3通过1失败，异常处理错误及回溯凭据输出）。原任务UNKNOWN不变，新增模型调用0，**NOT_READY_FOR_HANDOFF**；本轮已停止，安装版解析流程未改。

历史模型任务：[单次编码模型对照dev33](docs/reusable-tool-safety/acceptance/20261009-coding-model-comparison/public-evidence/README.md)。固定Qwen2.5-Coder 32B Q4_K_M，唯一正式安装页面任务1次生成、1候选、1次验收UNKNOWN（候选含代码围栏、语法错误，必要测试未执行）。没有合格修复，**NOT_READY_FOR_HANDOFF / MODEL_COMPARISON_CLOSED_UNSUCCESSFUL**；本轮已结束，暂停自动生成优化，等待用户决定。不启动5060。


系统检查工具是否把凭据写入输出、读取规定目录之外的文件或请求未授权服务，并用必要业务测试确认正常任务仍然成立；本地大模型只在已确认的问题上提出候选修复，程序负责验收、导出和复检。

独立开发分支 `feat/reusable-tool-safety` 增加了一个面向小型授权 Python 工具的共同入口：在 WSL/bubblewrap 副本中收集 pytest 和配置入口，观察目录越界读取、未授权 loopback HTTP 访问及合成凭据输出，并可导出以后重复运行的 pytest 回归断言。完整命令、外部 python-dotenv 接入和已覆盖边界见 [可复用工具安全开发说明](docs/reusable-tool-safety/README.md)。

当前增强初赛候选版 **`0.2.0-preliminary.9`**：从深色作品首页进入 h01、h03、h07 三个精选案例，或在启动时登记的合成项目上查看范围、执行无模型检查和导出回归测试；页面显示凭据、文件、网络、业务四类结果和对象适用性。[初赛候选入口](docs/preliminary-candidate/README.md)集中提供说明书、摘要、机制图、启动方式和通俗讲解；[一页展示顺序与录屏分镜](docs/preliminary-candidate/presentation-guide.md)可直接用于排练。

本版是已有能力的整合交付，未新增漏洞类别、模型实验或通用平台功能；导出回归新增对“实际生成安全报告”的结构化核对。[价值主张](docs/preliminary-candidate/value-and-innovation.md)、[通俗讲解](docs/preliminary-candidate/plain-guide.md)及[证据索引](docs/preliminary-candidate/evidence-index.md)解释为谁解决什么；[开发者体验包](docs/preliminary-candidate/experience-packet/README.md)仍待真人执行。

三个特点：**证据驱动的候选生成与反馈调整；程序控制的修改权限与安全/业务验收；对应修复对象的材料导出与复检。**

在本代码树根目录，用普通 Python 启动明确标注的真实历史回放（默认只读查看，不要求模型或 WSL）：

```powershell
python -m agent_pilot.launch --demo --mode view
```

打开 `http://127.0.0.1:8765/`。h01、h03、h07 均标为 **REPLAY**，不会因打开页面而调用模型。现场运行是单独操作，要求已准备的本地模型和可信隔离设施；材料复检需要隔离设施，但不需要 GPU 或模型。只读环境检查使用 `python -m agent_pilot.preflight`，配置和首次准备边界见候选说明。

现场 Agent 不应使用系统 Python 直接启动。Windows 首次准备运行
`scripts\setup-local-agent.cmd`，它会在 `.venv` 中安装锁定的
`agent_pilot\requirements-lock.txt`，确认 `qwen-agent==0.0.34` 可导入，并下载固定的
Gitleaks 8.28.0（官方 checksum 校验）。之后使用 `check-runtime.cmd` 或
`start-live.cmd`；它们会优先选择 `.venv\Scripts\python.exe`。完整测试示例：

```powershell
$env:CREDPROOF_GITLEAKS = (Resolve-Path .tools/gitleaks-8.28.0/gitleaks.exe).Path
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m unittest discover -s agent_pilot/tests -v
```

本轮文稿统一引用同一冻结批次的八个合成案例，不把后续已知案例复测拼入成绩。模型可能误判，固定流程也能解决多项案例；本作品不宣称通用漏洞修复、任意项目支持或 Agent 全面领先。

前版接入 [Twine 历史配置泄露组件接入](docs/external-scenario/twine/README.md)、[三种启动入口](docs/preliminary-candidate/startup-modes.md)、[一页贡献与代码对应](docs/preliminary-candidate/contribution-map.md)、[真实演示视频](docs/preliminary-candidate/video/README.md)及 [源码讲解](docs/preliminary-candidate/source-walkthrough.md)。外部结果单列，原八例完整统计不变。

## 历史阶段入口

以下保留原阶段的实现、失败和评审口径，其启动命令、固定机器路径和阶段状态以当时版本为准：

- [原始验收器研发评审 0.1.0-review.1](docs/review/README.md)
- [本地 Agent 首轮评审](docs/local-agent/reliability/README.md)
- [本地 Agent 工具调用协议修订评审](docs/local-agent/tool-call-revision/README.md)
- [早期初赛定位](docs/preliminary/00_positioning_and_plan.md)与 [V2 方案原型](docs/plan-v2/README.md)

开源基础、实际 AI 参与和资格待确认项见 [来源披露](docs/local-agent/reliability/source-attribution.md)及 [候选模板核查](docs/preliminary-candidate/template-requirements.md)。模型权重、真实凭据和本机运行设施不随源码包提供。
