# CredProof 需求—实现—证据验收表（dev19）

本表对应本版源码提交（完整 SHA 在 GitHub 评审入口及后续交付收据中固定）；验收资料随后在提交中固化。它用于外部复查，不表示模型修复成功或参赛资格已验收。

状态含义：`IMPLEMENTED_VERIFIED` 表示本轮有实际命令和材料；`IMPLEMENTED_UNVERIFIED` 表示代码/历史测试存在但本轮缺少新实测；`FAILED_OR_BLOCKED` 表示交接前必须补齐或保持禁用。

| 编号 | 要求 | 状态 | 实现与证据 | 仍缺什么 |
|---|---|---|---|---|
| R01 | 项目初始化与配置 | `IMPLEMENTED_VERIFIED` | `credproof_safety/config.py:template/load_config；credproof_safety/cli.py:init`；acceptance/20261006-final/logs/init-stdout.txt；tests/test_reusable_tool_safety.py | 只支持当前配置模式；配置仍需开发者确认 |
| R02 | 授权外部项目与pytest复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:check_project；examples/external/python-dotenv-v1.2.2`；acceptance/20261006-final/before-report.json；acceptance/20261006-final/fixed-report.json；acceptance/20261006-final/import-origin-sanitized.txt | 这是一个授权外部快照和人工注入适配，不是上游漏洞或企业部署 |
| R03 | 凭据输出观察 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:output capture；credproof_safety/project.py:_verdict`；acceptance/20261006-final/before-report.json；acceptance/20261006-final/fixed-report.json；experiments/reusable-tool-safety/20261003-observer-fix-v1/import-output.json | 不覆盖原生扩展、私有 logger sink 或所有子进程通道 |
| R04 | 文件边界 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:audit path normalization；credproof_safety/project.py:_verdict`；acceptance/20261006-final/consumer/fixed-consumer-junit.xml；acceptance/20261006-final/consumer/reintroduced-defect-consumer-junit.xml；acceptance/20261006-final/fixed-report.json | Python audit 观察尝试并结合受控入口证据；不等同 Windows 内核审计 |
| R05 | 网络边界 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:mock services/socket audit；credproof_safety/project.py:_verdict`；experiments/reusable-tool-safety/20261003-targeted-fix-07/allowed_file_redirect.json；experiments/reusable-tool-safety/20261003-targeted-fix-07/reintroduced_file_bypass.json | 不宣称公网 SSRF、DNS、原生 syscall 或 Windows 内核网络审计 |
| R06 | 必要业务测试真实完成与通过 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:CredProofPytestObserver；credproof_safety/project.py:_verdict`；_runs/current-pytest-observer/；agent_pilot/tests/test_runtime_config.py | 只对声明的必要用例语义负责；递归包装 skip 由执行侧区分 |
| R07 | 单页项目注册、检查、总体判决与分项 | `IMPLEMENTED_VERIFIED` | `agent_pilot/project_workspace.py；agent_pilot/web.py；credproof_safety/web_repair.py`；`acceptance/20261006-final/page-flow.md`；`acceptance/20261006-page-live-boundary/summary.json` | 目前只有登记案例 p01 映射到资料助手固定项目；p02–p06 仍只提供历史回放 |
| R08 | 候选修复授权与修改边界 | `IMPLEMENTED_UNVERIFIED` | `credproof_safety/agent.py:serve`；`credproof_safety/web_repair.py:execution_summary`；`acceptance/20261006-page-live-boundary/page-live-record.json`；`acceptance/20261006-live-correction/live-statistics-correction.json`；`acceptance/20261007-agent-effect/run-summary.json` | 授权、工具往返、可信判决和停止处理已有真实证据；本次冻结 p01 运行实际为 4 次模型尝试、3 份 usage、6 次工具请求、0 个接受候选、1 次 FAIL 验收并以超时 INCOMPLETE 结束，仍无模型修复成功证据 |
| R09 | 对象、报告适用性与复检 | `IMPLEMENTED_VERIFIED` | `agent_pilot/web.py:object/applicability checks；credproof_safety/project_bundle.py；credproof_safety/tests/test_project_bundle.py；acceptance/20261006-live-correction/new-project-bundle/；acceptance/20261006-live-correction/public-project-bundle-dev17/；acceptance/20261006-live-correction/public-project-recheck-dev17.json` | 首次导出核对当前候选树、配置、入口和必要测试；公开派生 bundle 按固定 Git blob 字节生成并在新目录复检。旧历史 bundle 与 `project-public-bundle/v1` 分流；哈希是完整性绑定，不是密码学证明或第三方认证 |
| R10 | 导出与项目内复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:export_regression_tests；scripts/run-exported-regression-check.py`；acceptance/20261006-final/consumer/；acceptance/20261006-final/exported-tests/；acceptance/20261006-final/summary.json | 受控 WSL/bubblewrap 依赖需在消费者机器准备 |
| R11 | 清洁安装、启动与隔离预检 | `IMPLEMENTED_VERIFIED` | `pyproject.toml package-data；agent_pilot/preflight.py；agent_pilot/launch.py；agent_pilot/web.py:launch_command`；acceptance/20261006-final/wheel-manifest.json；acceptance/20261006-final/import-origin-sanitized.txt；acceptance/20261006-final/preflight-summary.json；acceptance/20261006-final/page-flow.md | 跨机器、非 WSL 环境未承诺；现场页面必须通过 `CREDPROOF_INSTALLED_PYTHON` 或 local-runtime 的 `program_python` 指定已核验安装解释器，不再回退历史 `_runs` |
| R12 | 模型进程文件系统/网络边界独立证明 | `IMPLEMENTED_VERIFIED` | `credproof_safety/agent.py:_MODEL_BOUNDARY_BOOTSTRAP`；`acceptance/20261006-model-boundary/model-boundary-probe.raw.json`；`acceptance/20261006-page-live-boundary/page-live-record.json` | 只覆盖一次授权合成项目和一次页面任务；不等同通用沙箱或内核级审计 |
| R13 | 模型本地/零付费API运行 | `IMPLEMENTED_VERIFIED` | `credproof_safety/web_repair.py`；`agent_pilot/model_client.py`；`acceptance/20261006-page-live-boundary/summary.json` | 本次页面任务由 Ollama 报告为 CPU；主机为 RTX 5090，但未测量 GPU 性能；作品运行未调用付费 API |

## 本轮页面现场链路

`agent_pilot/web.py:launch_command` 不再调用默认阻断的 `agent_pilot.offline_run`。登记的 `p01` 由服务端固定映射到 `examples/material_assistant/credproof.toml`，页面启动的子进程运行 `credproof_safety.web_repair`，再由 `credproof_safety.agent.request_repair` 打开现有 WSL/bubblewrap 模型边界。适配器将项目身份、候选副本、最终可信报告和任务终态写回页面的 `C-agent` 记录；浏览器仍不能提交路径、命令、代码或判决。p02–p06 没有新的适配时，服务端明确返回“仅历史回放”，不把旧 fixtures 伪装成现场任务。

5090 主机上的真实 HTTP 任务记录见 [`acceptance/20261006-page-live-boundary/`](acceptance/20261006-page-live-boundary/)。HTTP POST 返回 202，supervisor 退出码 0；模型实际尝试 6 次、服务报告 usage 5 份、native 工具请求 7 次，执行器实际接受 1 份候选并验收 1 次，可信最终验收为 `FAIL`，任务为 `INCOMPLETE`。页面显示该项目与模型边界状态，未用历史回放替代本次任务。详见 [`acceptance/20261006-live-correction/live-statistics-correction.json`](acceptance/20261006-live-correction/live-statistics-correction.json)。
## 2026-10-07 受限效果复测

在提交 `e90a472` 固定的上下文索引修正后，对同一登记资料助手 `p01` 只运行一次新的有限任务。`get_evidence` 已列出 `tool.py` 和 `tests/test_business.py`，并提供正常业务、允许拒绝方式和凭据输出规则；模型仍先猜测两个不存在路径，随后读取真实文件，并在提交候选前调用一次可信验收。该验收仍为原问题 `FAIL`；没有接受候选，模型第 4 次请求在单请求 120 秒墙钟限制下超时，任务为 `INCOMPLETE`。本次独立统计为 4/3/6/0/1（模型尝试/usage/工具请求/接受候选/验收），不与旧页面批次的 6/5/7/1/1 拼接。完整脱敏轨迹见 [`acceptance/20261007-agent-effect/`](acceptance/20261007-agent-effect/)。

## 本轮清洁安装链路

冻结源码后构建 `credproof_safety-0.3.0.dev18-py3-none-any.whl`，在仓库外短路径新建 venv，安装 wheel 与 pytest；导入路径指向 `site-packages`。外部 python-dotenv 副本依次执行 init、漏洞 check（FAIL）、修复 check（PASS）、导出。导出测试放入三个消费者副本，用正常 pytest 发现并执行：fixed `1 passed`，重新引入文件边界缺陷 `1 failed`，无关文件变化 `1 passed`；fixed 第二次执行仍退出0并生成第二份报告。页面在 `127.0.0.1:18773` 通过浏览器完成“查看范围→现场检查·无模型→导出安全测试”，可见总体 PASS、四项分项 PASS、对象/时间/适用性和导出提示。

## 模型与隔离边界

本版有一次模型边界探针运行，以及一次从单页真实发起的模型任务。模型进程自身使用独立 bubblewrap allowlist 和私有 network namespace；页面任务的探针记录只有 `lo`、外网地址均失败、宿主哨兵不可见、代码只读，并确认 Ollama 继承同一 namespace。页面任务通过 native WSL RPC 与可信执行器通信，公开副本仅保存脱敏请求/响应记录。该次任务调用 6 次模型、服务返回 5 份 usage、7 次工具请求，实际接受 1 个候选并验收 1 次，最终可信验收为 `FAIL`，任务以 `INCOMPLETE` 结束；这不能写成自动修复成功。程序权限 gate、候选预算和终止条件由执行器管理，模型不能读取标签、历史结果或参考补丁。Ollama 日志记录本次计算设备为 CPU；主机是 RTX 5090，仅作为运行环境记录，不作 GPU 性能结论。

边界逐项记录位于 [`acceptance/20261006-model-boundary/`](acceptance/20261006-model-boundary/)，页面现场记录位于 [`acceptance/20261006-page-live-boundary/`](acceptance/20261006-page-live-boundary/)。本版状态为“可供外部定向复验”：模型进程边界和页面接线已有一次真实证据，但 Agent 修复效果仍只按失败的有限运行如实记录。

## 排除项

五页平台、历史扫描、多语言、真实凭据、公网目标、多 Agent 和新案例集不属于本轮必需交付；它们不计入未完成必需项。

