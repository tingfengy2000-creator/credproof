# dev33 有限编码模型对照：收尾记录

收尾日期：2026-10-10。**本轮已结束，NOT_READY_FOR_HANDOFF / MODEL_COMPARISON_CLOSED_UNSUCCESSFUL。** 本页只核对既有结果、补充交付入口；没有新模型调用、候选执行或复检，没有启动下一轮实验或5060交接。

## 身份与计数

- 实际模型：`qwen2.5-coder:32b-instruct-q4_K_M`，manifest digest `b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41`。Ollama 0.34.4，模型原生模板、本台5090 CUDA0、既有白名单/私有网络边界。
- 被测源码：`a780b9e6543355c2108c1d41e43a8dccd7c2e0c1`。安装wheel构建源：`ad826dae2d43ee0c0ec636f59a48f9325bcd14df`；受影响12份安装程序文件与冻结源码一致。此前交付：`68ac5b240bd0c38317bff61e8fd1c2b96b608794`；本次仅追加收尾文档，未改变被测程序。
- 登记任务：`assistant-original/p01`；页面任务ID：`live-c5e9217f868f4681a94bdda49c914e6e`。
- 非项目结构化预检：1次请求，通过。正式任务：1个、1次模型请求/1份usage、1次生成、1份不同且被接受的候选、1次程序自动验收、0次格式纠正、0次native工具调用、0次NO_CHANGE。合计模型请求2次，预检与正式任务分开统计。
- 终态：候选验收 `UNKNOWN`，任务 `STOPPED_UNKNOWN_VERIFICATION`。页面/子进程正常结束、退出0，不表示修复任务成功。调用/候选额度未耗尽；既有流程遇UNKNOWN即停止，未使用剩余额度重新生成。

## 完成与未执行

| 步骤 | 实际状态 | 对应材料 |
|---|---|---|
| 官方固定模型下载、Windows/WSL完整blob校验 | 已完成；旧模型保留 | [下载收据](public-evidence/preparation/download-receipt.json)、[WSL校验](public-evidence/preparation/native-model-install.json) |
| 模型/manifest薄适配与必要软件回归 | 已完成；未修改原任务、组件API、工作包构造和验收规则 | [版本及工作包来源](public-evidence/preparation/work-package-equivalence.json)、[软件回归范围](public-evidence/preparation/regression-provenance.json) |
| 非项目结构化预检 | 已完成1次 | [请求](public-evidence/structured-preflight/request.json)、[响应](public-evidence/structured-preflight/response.json)、[模型设备](public-evidence/structured-preflight/receipt.json) |
| 安装页面发起唯一正式任务 | 已完成；使用本次模型与安装程序，没有历史回放替代 | [冻结计划](public-evidence/formal-page/freeze.json)、[页面启动](public-evidence/formal-page/page-command.json)、[页面最终记录](public-evidence/formal-page/page-final.json) |
| 候选生成及原检查器自动验收 | 已完成1次，UNKNOWN | [实际请求](public-evidence/model-trace/model-01-request.json)、[响应](public-evidence/model-trace/model-01-response.json)、[完整候选](public-evidence/candidates/candidate-01.py)、[完整验收报告](public-evidence/candidates/verification-01.json) |
| 同一合格候选/组件/策略导出 | **未执行**：没有合格候选 | 没有本轮成功bundle，未用旧成功或人工控制补齐 |
| 同候选匿名取回后新目录无模型PASS复检 | **未执行**：没有可信PASS对象 | 没有本轮PASS复检报告 |
| 已有失败证据的Git字节清单与匿名取件 | 已完成；取件不等于动态复检 | [公开字节清单](public-evidence/published-manifest.json)、[100份取件收据](github-publication.json) |
| 安装程序和页面对应 | 已完成本次实际调用及UNKNOWN记录的来源核对；成功效果入口未成立 | [安装收据](public-evidence/preparation/install-final-receipt.json)、[主进程来源](public-evidence/preparation/installed-program-origin-final.json)、[实际子进程来源](public-evidence/formal-page/installed-child-origin.json)、[源码一致性](public-evidence/closure/program-source-equivalence.json) |

## 具体失败与边界

模型返回的JSON符合原schema，但`code`包含字面量Markdown围栏。实际Python在候选第1行报SyntaxError，pytest退出2，必要测试收集0/执行0，入口场景执行0；因此UNKNOWN，不能宣称正常业务、输出凭据、文件边界或网络/重定向条件已经通过。没有剥除围栏、手工补代码、改提示词或重跑任务。

源码中确实增加了组件调用，保留正确的凭据变量名读取表达式，并移除了日志/返回中的凭据表达式；这些是静态变化，不是动态修复证据。另有静态问题：第26—27行引用未绑定的`urllib`，并将要求保留的HTTPError改抛ValueError；未执行这些路径，不能倒填动态FAIL。

本轮直接阻断来自**模型生成的无效源码格式**，继而使必要检查无法执行；不是下载、隔离启动、推理设备、超时或输入预算失败。原解析器仅校验JSON数据结构，没有提前识别Python代码围栏；本轮未修改它或改变UNKNOWN停止协议来追加尝试。本次不是有效可执行补丁的语义能力排名。

仍缺：当前真实模型合格候选、同对象公开取件后的无模型PASS复检，以及成功效果对应的最终入口依据。故不是“仅待外部复核”，也不申请READY。原初赛候选、旧模型、全部历史失败及原件保留。

## 交付与停止

[现有评审README](README.md)、[一页结论及完整证据](public-evidence/README.md)、[真实计数](public-evidence/closure/conclusion.json)、[命令及退出码](public-evidence/closure/commands.json)、[原始/派生字节来源](public-evidence/closure/request-provenance.json)。公开材料已结构化脱敏，模型权重、rootfs、虚拟环境和真实凭据不入Git。

本次只将本页及README入口推送`feat/reusable-tool-safety`，不改main、不强推、不创建Release、不覆盖旧标签或包。此前100份公开正文和最终交付9份关键Raw已核对，适用结果直接引用；本次仅核对新增收尾入口及固定提交关键Raw，不重跑实验或整套取件。

**本轮到此停止。暂停自动生成效果优化，等待用户裁定后续资源或产品范围；不自行降低原要求，不启动5060。**
