# CredProof 需求—实现—证据验收表（dev14）

本表对应源码提交 `ebb5afa`（证据提交完成后在交付收据补充完整 SHA）。它用于外部复查，不表示模型边界或参赛资格已验收。

状态含义：`IMPLEMENTED_VERIFIED` 表示本轮有实际命令和材料；`IMPLEMENTED_UNVERIFIED` 表示代码/历史测试存在但本轮缺少新实测；`FAILED_OR_BLOCKED` 表示交接前必须补齐或保持禁用。

| 编号 | 要求 | 状态 | 实现与证据 | 仍缺什么 |
|---|---|---|---|---|
| R01 | 项目初始化与配置 | `IMPLEMENTED_VERIFIED` | `credproof_safety/config.py:template/load_config；credproof_safety/cli.py:init`；acceptance/20261006-final/logs/init-stdout.txt；tests/test_reusable_tool_safety.py | 只支持当前配置模式；配置仍需开发者确认 |
| R02 | 授权外部项目与pytest复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:check_project；examples/external/python-dotenv-v1.2.2`；acceptance/20261006-final/before-report.json；acceptance/20261006-final/fixed-report.json；acceptance/20261006-final/import-origin-sanitized.txt | 这是一个授权外部快照和人工注入适配，不是上游漏洞或企业部署 |
| R03 | 凭据输出观察 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:output capture；credproof_safety/project.py:_verdict`；acceptance/20261006-final/before-report.json；acceptance/20261006-final/fixed-report.json；experiments/reusable-tool-safety/20261003-observer-fix-v1/import-output.json | 不覆盖原生扩展、私有 logger sink 或所有子进程通道 |
| R04 | 文件边界 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:audit path normalization；credproof_safety/project.py:_verdict`；acceptance/20261006-final/consumer/fixed-consumer-junit.xml；acceptance/20261006-final/consumer/reintroduced-defect-consumer-junit.xml；acceptance/20261006-final/fixed-report.json | Python audit 观察尝试并结合受控入口证据；不等同 Windows 内核审计 |
| R05 | 网络边界 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:mock services/socket audit；credproof_safety/project.py:_verdict`；experiments/reusable-tool-safety/20261003-targeted-fix-07/allowed_file_redirect.json；experiments/reusable-tool-safety/20261003-targeted-fix-07/reintroduced_file_bypass.json | 不宣称公网 SSRF、DNS、原生 syscall 或 Windows 内核网络审计 |
| R06 | 必要业务测试真实完成与通过 | `IMPLEMENTED_VERIFIED` | `credproof_safety/runner.py:CredProofPytestObserver；credproof_safety/project.py:_verdict`；_runs/current-pytest-observer/；agent_pilot/tests/test_runtime_config.py | 只对声明的必要用例语义负责；递归包装 skip 由执行侧区分 |
| R07 | 单页项目注册、检查、总体判决与分项 | `IMPLEMENTED_VERIFIED` | `agent_pilot/project_workspace.py；agent_pilot/web.py:renderProjectModes/project check APIs`；acceptance/20261006-final/page-flow.md | 本轮只验证 recheck/no-model；未启动 live Agent |
| R08 | 候选修复授权与修改边界 | `IMPLEMENTED_UNVERIFIED` | `credproof_safety/agent.py:serve；agent_pilot/tools.py:dispatch；agent_pilot/tests/test_reliability.py`；_runs/current-final-agent-boundary-tests/pytest.txt；agent_pilot/tests/test_reliability.py；experiments/reusable-tool-safety/20261004-external-dotenv-agent-v2/summary.json | 本轮没有新的模型修复；不能把程序 gate 通过写成 Agent 修复成功 |
| R09 | 对象、报告适用性与复检 | `IMPLEMENTED_VERIFIED` | `agent_pilot/web.py:object/applicability checks；agent_pilot/tests/test_web_material_binding.py；agent_pilot/bundle.py`；agent_pilot/tests/test_web_material_binding.py；acceptance/20261006-final/page-flow.md | 哈希是完整性绑定，不是密码学证明或第三方认证 |
| R10 | 导出与项目内复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:export_regression_tests；scripts/run-exported-regression-check.py`；acceptance/20261006-final/consumer/；acceptance/20261006-final/exported-tests/；acceptance/20261006-final/summary.json | 受控 WSL/bubblewrap 依赖需在消费者机器准备 |
| R11 | 清洁安装、启动与隔离预检 | `IMPLEMENTED_VERIFIED` | `pyproject.toml package-data；agent_pilot/preflight.py；agent_pilot/launch.py`；acceptance/20261006-final/wheel-manifest.json；acceptance/20261006-final/import-origin-sanitized.txt；acceptance/20261006-final/preflight-summary.json；acceptance/20261006-final/page-flow.md | 跨机器、非 WSL 环境未承诺 |
| R12 | 模型进程文件系统/网络边界独立证明 | `FAILED_OR_BLOCKED` | `agent_pilot/offline_run.py:local model namespace；agent_pilot/runtime_config.py；preflight saved probe`；acceptance/20261006-final/preflight-summary.json；docs/reusable-tool-safety/README.md#agent-边界 | 候选 bubblewrap 隔离不等于模型进程全文件系统隔离；在该证据补齐前禁止外部交接/现场模型运行 |
| R13 | 模型本地/零付费API运行 | `IMPLEMENTED_UNVERIFIED` | `agent_pilot/offline_run.py；agent_pilot/model_client.py`；acceptance/20261006-final/preflight-summary.json；agent_pilot/model_client.py | 新模型调用和离线出网限制未在本轮重跑 |

## 本轮清洁安装链路

冻结源码后构建 `credproof_safety-0.3.0.dev14-py3-none-any.whl`，在仓库外短路径新建 venv，安装 wheel 与 pytest；导入路径指向 `site-packages`。外部 python-dotenv 副本依次执行 init、漏洞 check（FAIL）、修复 check（PASS）、导出。导出测试放入三个消费者副本，用正常 pytest 发现并执行：fixed `1 passed`，重新引入文件边界缺陷 `1 failed`，无关文件变化 `1 passed`；fixed 第二次执行仍退出0并生成第二份报告。页面在 `127.0.0.1:18773` 通过浏览器完成“查看范围→现场检查·无模型→导出安全测试”，可见总体 PASS、四项分项 PASS、对象/时间/适用性和导出提示。

## 模型与隔离边界

本轮未启动新的 Agent 推理。程序工具权限、候选预算和对象漂移 gate 有单元测试；候选副本可在既有 bubblewrap 中检查。模型进程本身没有独立的只挂载白名单与出网探针，preflight 也明确记录 `model_executed=false`、`network_probe_performed=false`。因此本轮交付状态为 `NOT_READY_FOR_HANDOFF`，不得把候选副本隔离描述成模型全进程隔离，也不得现场启用 live repair。

## 排除项

五页平台、历史扫描、多语言、真实凭据、公网目标、多 Agent 和新案例集不属于本轮必需交付；它们不计入未完成必需项。
