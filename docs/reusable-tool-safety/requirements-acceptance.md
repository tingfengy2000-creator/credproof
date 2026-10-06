# CredProof 需求—实现—证据验收表（dev15）

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
| R07 | 单页项目注册、检查、总体判决与分项 | `IMPLEMENTED_VERIFIED` | `agent_pilot/project_workspace.py；agent_pilot/web.py:renderProjectModes/project check APIs`；acceptance/20261006-final/page-flow.md | 现场页面仍需显式配置当前白名单模型入口；旧 offline harness 默认阻断 |
| R08 | 候选修复授权与修改边界 | `IMPLEMENTED_UNVERIFIED` | `credproof_safety/agent.py:serve；agent_pilot/tools.py:dispatch；agent_pilot/tests/test_reliability.py`；_runs/current-final-agent-boundary-tests/pytest.txt；agent_pilot/tests/test_reliability.py；experiments/reusable-tool-safety/20261004-external-dotenv-agent-v2/summary.json | 本轮没有新的模型修复；不能把程序 gate 通过写成 Agent 修复成功 |
| R09 | 对象、报告适用性与复检 | `IMPLEMENTED_VERIFIED` | `agent_pilot/web.py:object/applicability checks；agent_pilot/tests/test_web_material_binding.py；agent_pilot/bundle.py`；agent_pilot/tests/test_web_material_binding.py；acceptance/20261006-final/page-flow.md | 哈希是完整性绑定，不是密码学证明或第三方认证 |
| R10 | 导出与项目内复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:export_regression_tests；scripts/run-exported-regression-check.py`；acceptance/20261006-final/consumer/；acceptance/20261006-final/exported-tests/；acceptance/20261006-final/summary.json | 受控 WSL/bubblewrap 依赖需在消费者机器准备 |
| R11 | 清洁安装、启动与隔离预检 | `IMPLEMENTED_VERIFIED` | `pyproject.toml package-data；agent_pilot/preflight.py；agent_pilot/launch.py`；acceptance/20261006-final/wheel-manifest.json；acceptance/20261006-final/import-origin-sanitized.txt；acceptance/20261006-final/preflight-summary.json；acceptance/20261006-final/page-flow.md | 跨机器、非 WSL 环境未承诺 |
| R12 | 模型进程文件系统/网络边界独立证明 | `IMPLEMENTED_VERIFIED` | `credproof_safety/agent.py:_MODEL_BOUNDARY_BOOTSTRAP`；`acceptance/20261006-model-boundary/model-boundary-probe.raw.json`；`model-boundary-plan.raw.json`；`model-run-summary.json` | 只覆盖一次授权合成项目运行；不等同通用沙箱或内核级审计 |
| R13 | 模型本地/零付费API运行 | `IMPLEMENTED_VERIFIED` | `acceptance/20261006-model-boundary/model-run.raw.json`；`ollama-stderr.raw.log`；`model-run-summary.json` | 本次运行探测为 CPU，未测量 GPU 性能；作品运行未调用付费 API |

## 本轮清洁安装链路

冻结源码后构建 `credproof_safety-0.3.0.dev14-py3-none-any.whl`，在仓库外短路径新建 venv，安装 wheel 与 pytest；导入路径指向 `site-packages`。外部 python-dotenv 副本依次执行 init、漏洞 check（FAIL）、修复 check（PASS）、导出。导出测试放入三个消费者副本，用正常 pytest 发现并执行：fixed `1 passed`，重新引入文件边界缺陷 `1 failed`，无关文件变化 `1 passed`；fixed 第二次执行仍退出0并生成第二份报告。页面在 `127.0.0.1:18773` 通过浏览器完成“查看范围→现场检查·无模型→导出安全测试”，可见总体 PASS、四项分项 PASS、对象/时间/适用性和导出提示。

## 模型与隔离边界

本版有一次新的真实模型进程运行。模型进程自身使用独立 bubblewrap allowlist 和私有 network namespace；探针记录只有 `lo`、外网三地址均失败、宿主哨兵不可见、代码只读。模型通过 native WSL RPC 目录与可信执行器通信，公开副本仅保存脱敏请求/响应记录。运行中模型调用 11 次工具、提交 3 个候选，三次可信验收均为 `FAIL`，任务以 `INCOMPLETE` 结束；这不能写成自动修复成功。程序权限 gate 和候选预算仍由执行器管理，模型不能读取标签、历史结果或参考补丁。

边界逐项记录位于 [`acceptance/20261006-model-boundary/`](acceptance/20261006-model-boundary/)。本版状态为“可供外部定向复验”：模型边界阻断已补齐，但 Agent 修复效果仍只按这一次有限运行如实记录。

## 排除项

五页平台、历史扫描、多语言、真实凭据、公网目标、多 Agent 和新案例集不属于本轮必需交付；它们不计入未完成必需项。
