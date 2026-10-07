# CredProof 需求—实现—证据验收表（dev23）

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
| R08 | 候选修复授权与修改边界 | `IMPLEMENTED_UNVERIFIED` | `credproof_safety/agent.py:_model_readable_paths/_phase_rejection/serve`; `credproof_safety/project.py:_scenario_requirements/_scenario_observation_gap`; `acceptance/20261007-return-redirect/`；`acceptance/20261007-return-redirect/context-budget-pilot/` | 预算预检三阶段均在16K内；正式任务12次模型请求/12份usage/15次工具请求尝试，候选1验收FAIL、候选2未验收，任务INCOMPLETE；没有模型PASS、导出或新目录复检 |
| R09 | 对象、报告适用性与复检 | `IMPLEMENTED_VERIFIED` | `agent_pilot/web.py:object/applicability checks；credproof_safety/project_bundle.py；credproof_safety/tests/test_project_bundle.py；acceptance/20261006-live-correction/new-project-bundle/；acceptance/20261006-live-correction/public-project-bundle-dev17/；acceptance/20261006-live-correction/public-project-recheck-dev17.json` | 首次导出核对当前候选树、配置、入口和必要测试；公开派生 bundle 按固定 Git blob 字节生成并在新目录复检。旧历史 bundle 与 `project-public-bundle/v1` 分流；哈希是完整性绑定，不是密码学证明或第三方认证 |
| R10 | 导出与项目内复用 | `IMPLEMENTED_VERIFIED` | `credproof_safety/project.py:export_regression_tests；scripts/run-exported-regression-check.py`；acceptance/20261006-final/consumer/；acceptance/20261006-final/exported-tests/；acceptance/20261006-final/summary.json | 受控 WSL/bubblewrap 依赖需在消费者机器准备 |
| R11 | 清洁安装、启动与隔离预检 | `IMPLEMENTED_VERIFIED` | `pyproject.toml package-data；agent_pilot/preflight.py；agent_pilot/launch.py；agent_pilot/web.py:launch_command`；acceptance/20261006-final/wheel-manifest.json；acceptance/20261006-final/import-origin-sanitized.txt；acceptance/20261006-final/preflight-summary.json；acceptance/20261006-final/page-flow.md | 跨机器、非 WSL 环境未承诺；现场页面必须通过 `CREDPROOF_INSTALLED_PYTHON` 或 local-runtime 的 `program_python` 指定已核验安装解释器，不再回退历史 `_runs` |
| R12 | 模型进程文件系统/网络边界独立证明 | `IMPLEMENTED_VERIFIED` | `credproof_safety/agent.py:_MODEL_BOUNDARY_BOOTSTRAP`；`acceptance/20261006-model-boundary/model-boundary-probe.raw.json`；`acceptance/20261006-page-live-boundary/page-live-record.json` | 只覆盖一次授权合成项目和一次页面任务；不等同通用沙箱或内核级审计 |
| R13 | 模型本地/零付费API运行 | `IMPLEMENTED_VERIFIED` | 历史页面批次与本轮 `acceptance/20261007-return-redirect/context-budget-pilot/public-evidence/ollama-stderr.txt`、`run-summary.json` 分开保存；本轮为 CUDA0/RTX 5090/12次模型请求/12份usage | 未调用付费 API；没有模型修复 PASS，不构成跨机器或稳定成功率结论 |

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

## 历史 Agent 顺序与正式修复效果（dev20，旧规则记录）

本轮只修正当前 Agent 的执行顺序和本地推理运行条件，旧实验与旧结论保留。首个模型请求现在携带由受控副本生成的有限索引、入口、测试文件和规则上下文；宿主端按依赖阶段拒绝越序调用：必须先取得证据，再读取声明文件，随后才能提交候选，只有已有接受候选时才能验收。没有接受候选时，`verify_patch` 返回 `NO_ACCEPTED_CANDIDATE`，不会对原代码副本冒充候选验收。

旧记录中的事实更正为：第1次响应在看到证据前同时提出了 `get_evidence` 和错误路径读取；第2次才读取真实 `tool.py` 与 `tests/test_business.py`；第3次验收的是原代码，因为此前没有接受候选；第4次在输入预算通过后由客户端等待 120 秒超时，原始记录没有服务端取消确认。

经过受控 CUDA 环境修正后，正式登记的 `assistant-original/p01` 运行实际使用 `CUDA0 / NVIDIA GeForce RTX 5090 / 31.8 GiB`。运行预算冻结为最多 12 次模型请求、3 个候选、1 次格式纠正、120 秒单请求和 900 秒任务墙钟；本次实际为 6 次模型请求、6 份 usage、7 次工具请求、2 个被接受候选和 2 次候选验收。候选 1 因仍有 `no_credential_output` 证据而 FAIL，候选 2 通过全部安全与业务检查。该候选随后导出为当前 project-bundle，并在新目录无模型复检 PASS。

这是一项固定合成任务的真实运行证据，不代表跨项目泛化、稳定成功率或所有风险类别均可自动修复。旧批次和 p02–p06 的历史回放不与本次结果合并；本轮不启动 5060 交接。


## 2026-10-07 返回值与跳转漏测修正（dev21）

本轮新增两个声明场景：允许文件+允许服务的真实返回必须不含合成凭据；允许文件+`/api/redirect` 必须产生允许服务观测，并满足声明的 `HTTPError`，否则为 `UNKNOWN` 或 `FAIL`。保存的 candidate-02 原样复测为 `FAIL`：正常返回仍含合成凭据，跳转观测到 `/api/redirect` 后又到达禁止 `/secret`。这份结果说明旧 PASS 只覆盖了旧入口，并不代表修复效果成立。

本目录的定向报告在 `acceptance/20261007-return-redirect/`。一次新的冻结模型任务及其候选导出/新目录复检尚待执行；在此之前本版保持 `NOT_READY_FOR_HANDOFF`。历史 8/10/20 版本记录不被改写或拼接。


## dev21 正式任务结果

返回值与跳转条件已由项目配置和可信执行器逐场景检查；原始版本、保存 candidate-02 均真实 `FAIL`。唯一一次新模型任务在 5090 的边界内取得 `get_evidence`、`read_code`、`read_code` 三个工具事件后，由保守输入预算停止，1 次模型请求/1 份 usage，0 个候选、0 次候选验收，任务 `INCOMPLETE`。停止原因是输入预算保护，不是服务端取消确认，也没有模型修复 PASS。保存 candidate-02 的 bundle 新目录复检仍为 `FAIL`。因此 R08 的修复效果继续为 `IMPLEMENTED_UNVERIFIED`，整体 `NOT_READY_FOR_HANDOFF`。


公开 bundle 复核：保存 candidate-02 的 Git blob 派生 bundle `public-saved-candidate02-bundle-dev21` 字节清单匹配，`project/tool.py` 为 LF/1808 bytes/SHA-256 `f7b017b6d8789dddc9231d89a3b0185713be9f869620262602e369b0b310a9a9`；从该公开目录新目录复检仍 `FAIL`。旧 dev20 bundle 仍独立保留，不能与本版两场景结果混用。


## dev22 上下文预算适配后的当前结论

正式模型运行所用源码提交为 `e6507f36b93a0a3168717cf7f09f439b57786132`；预算预检与材料冻结随后记录在 `2afd51bbd760a3e5d0aa01234e045c29d7e47f0e`。预检脚本使用实际客户端序列化和工具 schema，首请求、证据加两份源码、候选失败反馈三个阶段均 `within_declared_budget=true`，预检本身 `model_calls=0`。全套 `agent_pilot/tests` 实际为 `110 passed, 1 warning`。

正式 `assistant-original/p01` 只运行一次：12次模型请求、12份服务 usage、15次工具请求尝试（12次接受、3次因执行器上限拒绝）、2份接受候选。候选1完成可信验收并为 `FAIL`；候选2已保存但未验收；任务终态为 `INCOMPLETE`，停止原因为 `Model request budget exhausted`。没有 input-budget 超限事件，没有可信 PASS，因此没有同候选导出或新目录复检。详细入口为 [`acceptance/20261007-return-redirect/context-budget-pilot/README.md`](acceptance/20261007-return-redirect/context-budget-pilot/README.md)，脱敏逐次证据在其 `public-evidence/` 子目录。当前 `handoff_status` 仍为 `NOT_READY_FOR_HANDOFF`，5060 尚未启动。


## dev23 上下文保真与候选调度复测

本轮先对保存的 candidate-02 做了一次独立 `POST_RUN_VERIFICATION`，不调用模型、不改变原候选：pytest 4/4 通过，但常量返回没有读允许文件、没有取得允许服务回执/认证证据；跳转场景在 `ValueError` 处提前结束，未执行到跳转请求。因此该事后结果为 `FAIL`，原正式任务的 `UNVERIFIED` 仍保留。材料见 [`acceptance/20261007-return-redirect/context-budget-pilot/post-run-verification-candidate02-v1/`](acceptance/20261007-return-redirect/context-budget-pilot/post-run-verification-candidate02-v1/)。

压缩器现在按 `function_id` 将 assistant 工具调用与 function 结果成对选择：当前候选提交的源码正文、最新可信验收、必要测试读取和最新失败反馈保留；已脱离当前对象的重复成功日志可压缩。`REJECTED`、`ERROR`、`UNKNOWN`、预算耗尽和缺材料结果不改状态或 reason，也不再把入口源码替换成占位消息。提交新候选后由执行器立即调用可信 `check_project` 一次，记录 `program_auto_verify`；这不是模型工具调用，也不由模型文本判决。相同规范化 LF 源码记为 `NO_CHANGE`，不增加有效候选。

在当前 5090/CUDA0 边界内登记了同一 `assistant-original/p01` 的有限复测。v2 保留为发现工具预算停止缺口的原始记录；v3 在修正后实际运行 12 次模型请求、12 次工具请求、接受 1 个候选并由程序自动验收 1 次（`FAIL`），第 12 个工具结果用尽后任务以 `STOPPED_TOOL_BUDGET` 结束，没有继续消费新的模型请求。可信 PASS 为 0，没有导出或新目录 PASS。v3 结构化脱敏记录见 [`acceptance/20261007-return-redirect/context-budget-pilot-v3/`](acceptance/20261007-return-redirect/context-budget-pilot-v3/)。

因此 R08 的工程调度与上下文保真有协议和一次真实运行依据，但“当前模型产生合格修复、同一候选导出并在新目录复检 PASS”仍是 `IMPLEMENTED_UNVERIFIED`，整体维持 `NOT_READY_FOR_HANDOFF`。这不是稳定成功率或泛化结论。

## dev24：上下文最新读取保真（当前复审版）

本版源码提交：`16498c6`（当前工程修正）；本次有限正式模型运行冻结源码：`502072a1e20459bbf0e474ce0630c6cc22b6a842`。`compact_messages_for_budget` 通过真实函数调用 ID 保留最新读取对、当前候选正文、程序自动验收失败和最新 `executor_state`；主机以 `(path, current_candidate_sha256, last_verified_candidate, last_verdict)` 控制重复读取，第三次无新信息返回 `no_progress_same_read`。已有读取/候选后再次请求证据返回 `evidence_already_current`。这些改动由 `agent_pilot/tests/test_model_boundary.py` 和完整 Agent 测试覆盖；测试环境实际 `115 passed, 1 warning`。

v3 原始请求序列的无模型重放见 `acceptance/20261007-return-redirect/context-budget-pilot-v4/replay-summary.json` 及其 `payload-before.json`、`payload-after-read-05.json`、`payload-after-read-12.json`。8 个真实保存的入口读取均保持对应调用与返回、源码正文和主机计数，且请求摘要不再重复；预算预检四阶段均在 `14,848` 保守输入上限内。该重放不是模型成功或安全实验。

在 `502072a...` 上只运行一次 `assistant-original/p01`：5090/CUDA0、qwen3-coder:30b、既有模型边界；5 次模型请求、5 份 usage、6 次工具请求、1 个接受候选、1 次 `program_auto_verify`，候选为 `FAIL`，无 `PASS`、导出或新目录复检。第5次模型又请求已经完成的 `get_evidence`，客户端保守预算拒绝下一请求；原始失败保留。随后 `16498c6` 增加了重复证据阶段拒绝，仅做协议/单元回归，没有重跑模型。公开脱敏请求、响应、预算、候选和边界收据在 `acceptance/20261007-return-redirect/context-budget-pilot-v4/public-evidence/`。

因此 R08 的上下文保真、候选调度和重复阶段控制已有对应代码与协议证据；当前模型修复效果仍为 `IMPLEMENTED_UNVERIFIED`，整体 `NOT_READY_FOR_HANDOFF`。不把本轮的候选 FAIL、旧人工修复或历史 h03 拼成成功，5060 尚未启动。


## v5 上下文保真与预算同时可用的有限复测

源码提交 `2cf029ddb5adfa1bce40332906cb359a4e06a16b` 的压缩器保留当前源码、必要测试、候选失败反馈、最新 executor 状态和成对工具调用/返回；拒绝与错误语义不改写。重放与预算预检见 `acceptance/20261007-return-redirect/context-budget-pilot-v5/`，六个协议阶段均在 14,848 输入上限内，前缀结构变化使用完整 wire 字节回退。

同一 5090、`qwen3-coder:30b`、`assistant-original/p01` 只运行一次：8 次模型请求、8 份 usage、9 次工具请求、2 个接受候选、2 次程序自动验收；候选 1 和 2 均为 `FAIL`，第 9 次请求在输入预算保护处停止。没有可信 PASS、导出或新目录复检，状态继续 `NOT_READY_FOR_HANDOFF`，5060 尚未启动。
