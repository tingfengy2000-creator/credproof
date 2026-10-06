## 清洁安装与需求验收（dev16）

本版先完成清洁安装链路和可复核需求表，再决定是否交接 5060。入口文件是 [`requirements-acceptance.md`](requirements-acceptance.md) 与机器可读的 [`requirements-acceptance.json`](requirements-acceptance.json)。

- 清洁安装证据：[`acceptance/20261006-final/`](acceptance/20261006-final/)；包括 wheel、site-packages 导入来源、CLI before/fixed、浏览器实际操作、导出消费者 pytest/JUnit 和环境预检。
- 清洁安装发现的 wheel 静态资源缺口已在 `pyproject.toml` 修复，细节见 [`packaging-gap.md`](packaging-gap.md)。
- 无模型项目检查与导出记录见 [`page-flow.md`](page-flow.md)；模型现场入口的真实 HTTP 记录见 [`acceptance/20261006-page-live-boundary/`](acceptance/20261006-page-live-boundary/)。
- 当前状态：程序检查、导出链以及一次真实模型边界运行均有可读证据；本次模型任务本身按预算以 `INCOMPLETE` 结束，不能写成自动修复成功。

# CredProof reusable-tool-safety（0.3.0-dev.16）

本开发分支把 CredProof 的受控凭据验收扩展到两类实际工具行为：越过配置目录
读取文件、以及访问未授权的 HTTP 服务。它面向有源码和授权的小型 Python 工具，
使用一个版本化的 `credproof.toml` 和已有 pytest 测试。原初赛候选版仍在旧分支
和旧提交中保留，本页只记录新开发分支。

## 已实现的共同入口

源码包可用 `python -m pip install .` 安装；本轮在独立 Python 3.12 venv 中用
`setuptools` 构建 wheel `credproof_safety-0.3.0.dev14-py3-none-any.whl`，源码目录
本身也可直接运行 `python -m credproof_safety`。模型权重和 Ollama 不随 wheel 进入
安装包。

本地 Agent 测试必须使用 Python 3.12 的项目虚拟环境。Windows 可先运行
`scripts\setup-local-agent.cmd`；它按 `agent_pilot/requirements-lock.txt` 安装
`qwen-agent==0.0.34` 及其显式依赖（包括 `soundfile`、`tqdm`、`python-dateutil`），
再下载并校验 Gitleaks 8.28.0。直接使用系统 Python 可能出现 `qwen_agent` 可见但
`soundfile` 缺失，或把 Gitleaks 测试错误地显示为跳过。

```powershell
# 只预览，不覆盖已有配置
python -m credproof_safety init --project examples/material_assistant

# 在 WSL/bubblewrap 副本中收集 pytest，再执行配置的入口
python -m credproof_safety check --config examples/material_assistant/credproof.toml --output _runs/material-vulnerable.json

# 让本地 Qwen-Agent（已配置时）提出候选；模型缺失会返回 BLOCKED，不回退到付费 API
python -m credproof_safety repair --config examples/material_assistant/credproof.toml --output _runs/repair.json

# 导出以后可在项目中保留的模型无关 pytest 断言
python -m credproof_safety export-tests --config examples/material_assistant_fixed/credproof.toml --output _runs/exported-regression
```

`check` 不执行模型。原项目先复制到临时目录，pytest 的收集、`conftest.py` 导入、
插件加载和入口调用都在隔离副本内运行；只给出明确的项目代码、测试、合成文件和
loopback 模拟服务。缺少 WSL/bubblewrap/pytest 时返回 `UNKNOWN` 或 `BLOCKED`，不会
在宿主机降级运行未知项目。

`credproof.toml` 固定项目根、测试路径、入口、可修改范围、允许/禁止目录、允许服务、
合成凭据变量、必要的允许文件读取/服务凭据条件和运行限制。当前服务规则只接受隔离
环境中的一个 `127.0.0.1` 动态 HTTP mock，文件实验也固定为一个允许目录和一个禁止目录；
不满足该范围的配置会被拒绝，避免把未实现的网络/目录规则写成已验证。`expected_error`
只描述当前配置请求在攻击路径上的预期异常，不能替代 pytest 业务测试；正常返回也只有在
所有安全检查和业务测试都通过时才可能 PASS。规则由配置和程序验收器固定，模型不能修改规则、删除测试
或自行宣布通过。

## 接入自己的项目

开发者不需要改写入口为 CredProof 专用函数，也不需要复制一套裁判。最小流程是：

1. 在项目根目录执行 `python -m credproof_safety init --project .` 预览配置；确认后用
   `--write` 只创建不存在的 `credproof.toml`。
2. 填写项目测试路径、入口模块和函数、允许/禁止目录、允许的 loopback 服务、合成凭据
   环境变量、必要业务测试及 `mutable_scope`；真实秘密不写入配置。
3. 用 `python -m credproof_safety check --config credproof.toml --output .credproof/report.json`
   做不加载模型的检查。结果只有 `PASS`、`FAIL` 或因隔离/观察不足得到 `UNKNOWN`。
4. 需要修改时才运行 `repair`；模型只能提出候选，程序保留修改范围、重新执行测试和
   观察，不能由模型写入规则或宣布通过。
5. 用 `export-tests` 把模型无关的 pytest 断言放回项目，后续每次代码修改都重新读取当前
   对象并执行检查，不信任保存的旧报告。

初始化、检查、修复和导出都拒绝覆盖已有目标。pytest 收集、导入、`conftest.py` 和插件
加载均在受控副本中执行；未知项目缺少隔离材料时不会降级到宿主机运行。项目仍需人工
提供可信入口、允许目录/服务和必要业务测试，这些前置规则不由模型猜测。

`examples/ci/credproof-safety.yml.example` 是一个只允许手动触发、要求预先配置受控
self-hosted runner 的 CI 示例，不会自动启用，也不会把 GitHub 托管 runner 当作已验证
隔离环境。

## 真实受控结果

`scripts/run-reusable-safety-demo.py` 在三个 disposable 副本中运行同一流程：

| 副本 | 实际结果 | 含义 |
| --- | --- | --- |
| `examples/material_assistant` | `FAIL` | 真实读取禁止文件、跟随重定向到禁止 mock 服务、返回凭据 |
| `examples/material_assistant_fixed` | `PASS` | 业务 pytest 通过，允许文件和允许服务仍可用，凭据未输出 |
| fixed 副本重新引入文件检查缺陷 | `FAIL` | 同类回归重新被观测到 |

每次报告都区分 `ACTUAL_VIOLATION`、`OUTER_SANDBOX_BLOCKED` 和 `INCOMPLETE`。
目前的观测面是 Python `open`/`socket.connect` audit 事件及独立 mock HTTP 服务的
请求回执，并额外捕获可传播到根 logger 的 DEBUG 级 Python 日志；原生扩展直接系统调用、
私有 logger sink、TOCTOU、Windows 内核审计和完整 DNS/SSRF 语义仍列为未覆盖。项目自身的外部符号链接会被拒绝；实验目录中的越界符号链接仅在
宿主能够创建时纳入实验。`read then discard` 仍算读取违规。

## 外部项目接入

`examples/external/python-dotenv-v1.2.2` 是随评审包保存的上游快照，保留
`src/dotenv`、`tests/test_main.py`、`tests/conftest.py`、`LICENSE`、`pyproject.toml`
和 `README.md`，固定提交为 `36004e0e34be7665ff2b11a8a4005144f76f176d`，许可证为
BSD-3-Clause。`credproof_entry.py` 是明确标注的人工注入目录读取缺陷，不是上游漏洞、
CVE 或企业部署证据；`credproof_entry_fixed.py` 只增加授权目录约束并保留 dotenv 解析。

`scripts/run-external-dotenv-case.py` 会先把快照复制到操作系统临时目录，再从这个
仓库外的副本运行 before、fixed、reintroduced-defect 和 unrelated-change 四个结果，
不会直接把仓库内的 fixture 当作被测项目。命令为：

```powershell
python scripts/run-external-dotenv-case.py `
  --output experiments/reusable-tool-safety/external-dotenv-current
```

只有在已准备的 WSL、bubblewrap、审核过的 rootfs 和 Python site-packages 存在时，
才会得到 `before=FAIL`、`after=PASS`、`reintroduced_defect=FAIL`、
`unrelated_change=PASS`；缺少隔离材料时四项均应记录为 `UNKNOWN`，不能把环境阻断
写成代码通过。2026-10-04 的定向复测通过集中配置把 `~/credproof-agent-runtime`
解析为 WSL 内的绝对路径，真实完成了 117 个 pytest 测试（固定副本退出码 0），
并取得上述四项判定。该批次共收集 117 项测试，其中 114 项来自上游 `test_main.py`、3 项为本项目适配测试，
不是 117 项上游测试；注入版实际为 116 passed、1 failed、pytest 退出码 1。逐例记录保存在
`experiments/reusable-tool-safety/20261004-external-dotenv-v5/summary.json`；它仍只证明
一个外部项目、一个目录边界类别和人工注入缺陷，不是上游漏洞或泛化率结论。

资料助手的历史记录仍保存在 `experiments/reusable-tool-safety/20261003-final/`；
模型成功与不完整轨迹在同目录的 `agent-runs/` 下分开保存，不能拼成总体成功率。
WSL、bubblewrap、rootfs、Q4_K_M 模型和完整 Ollama digest 只在对应运行收据中记录；
权重不进入 Git。

外部 `python-dotenv` 副本还保留了两次真实本地 Agent 运行：
`experiments/reusable-tool-safety/20261004-external-dotenv-agent-v1/summary.json` 和
`20261004-external-dotenv-agent-v2/summary.json`。v1 的候选因入口业务行为未保持而
被判定 `FAIL`；v2 在收紧可读材料和反馈大小后，模型仍重复提交只检查文件存在性的补丁，
三次验收均未通过目录边界与凭据输出检查，最终以候选预算耗尽结束。它们不能与不调用模型的
`20261004-external-dotenv-v5` 检查结果拼成 Agent 成功；这些记录用于证明程序验收会拒绝
不合格补丁，并明确当前外部自动修复仍是待改进项。

`20261003-observer-fix/` 是后续的定向观测修正批次：执行器新增独立的
DEBUG 级 Python 日志通道，并以 `pytest -s` 避免测试输出掩盖泄露。该批次的
`vulnerable.json` 明确记录 `logs` 泄露，`fixed.json` 仍为 PASS，旧批次和旧
模型轨迹均未覆盖。此前模型成功轨迹是在日志观测修正前生成的，只能证明其当时
返回通道的候选修复，不能追溯宣称覆盖日志输出。

## 回归测试导出

导出的 `test_credproof_safety.py` 依赖已安装的 `credproof-safety` 包和项目中的
`credproof.toml`，每次重新运行当前副本并读取新观测，不信任保存的 PASS、网页或
案例 ID。可证明：漏洞版 FAIL、修复版 PASS、重新引入缺陷 FAIL、无关代码变更不会
仅因哈希变化失败。它不是签名、第三方认证或不可伪造证明；合成凭据和模拟服务
只支持这里声明的受控场景。

## Agent 边界

`repair` 只在当前副本已有对应类型的实际违规证据时开放 `submit_patch`，最多 12 次
模型调用和 3 个候选。工具调用必须是 Qwen-Agent/Ollama 的原生结构化调用；自然语言
中的函数名或 JSON 不会被执行。模型提出候选，程序执行 pytest、文件/网络观测和
修改范围检查，最终 verdict 由程序返回。作品本次运行不调用付费 API；模型权重在
仓库外，且需要既有本地 Ollama/Qwen 运行时。候选的检查由 bubblewrap 副本完成；本版另用独立的 bubblewrap 模型进程配置，
只挂载审核过的 Python 运行时、Qwen-Agent 依赖、Ollama 程序、固定 manifest/blob、
GPU 驱动只读目录和 `/work`、`/rpc` 受控目录。模型进程没有仓库、候选历史、参考补丁、
真实凭据或代理/API Key 环境；独立探针记录了只有 `lo`、三个外网地址均连接失败、宿主哨兵不可见、
模型代码挂载只读。模型边界证据与一次真实调用轨迹见本页下方的 2026-10-06 记录。
这仍不是公平盲测或通用隔离证明：模型运行只覆盖一个授权合成项目，本次三份候选都被可信验收判 `FAIL`，
任务按预算 `INCOMPLETE` 结束。

旧的 `agent_pilot.offline_run` 历史比较入口现在默认 fail-closed；它只保留历史记录，不再启动模型。页面的登记案例 `p01` 通过 `agent_pilot/web.py:launch_command` → `credproof_safety.web_repair` → `credproof_safety.agent.request_repair` 进入同一个白名单模型启动器，项目身份固定为 `assistant-original`，页面不会接受任意路径或命令。现场任务的真实终态仍由程序报告；本轮记录为 `INCOMPLETE` + `FAIL`，没有用历史回放替代，也没有把失败改写为修复成功。p02–p06 仍明确为历史回放入口。

## 当前边界

只承诺声明环境中的小型 Python 项目、一个配置入口和受控 pytest 测试；不支持任意
Shell、自动安装脚本、真实凭据、公网目标、云端撤销、多语言或通用 SSRF 证明。开发
者仍需人工确认允许目录、服务、入口、必要业务测试和修改范围。Windows 本机原始
路径、Windows 内核审计和跨机器部署尚未作全平台承诺。

## 2026-10-03 `feat/reusable-tool-safety` 定向修订

本轮只修观测、判定和可复查运行链，不扩大凭据、文件、网络类别。修订后的关键位置如下：

| 要求 | 实现位置 | 依据 |
| --- | --- | --- |
| 访问路径先规范化再分类 | `credproof_safety/runner.py` 的 `_script()` / `audit()` | `reintroduced_file_bypass.json` 捕获了 `/tmp/project/../lab/secrets/secret.txt`、相对路径和符号链接解析后的禁止目录尝试 |
| 观测字段缺失不得伪造 PASS | `credproof_safety/project.py` 的 `_execution_observation_error()` / `_verdict()` | `tests/test_reusable_tool_safety.py` 覆盖缺少 `credential_leaks`、`forbidden_reads`、`unauthorized_connections` 及错误类型，结果为 `UNKNOWN` |
| 凭据环境名真正生效 | `credproof_safety/runner.py` 的 `credential_env` 与 `check_project()` 传递 | `custom_credential_env.json` 使用 `CUSTOM_SYNTHETIC_CREDENTIAL` 并真实得到 `PASS` |
| 允许文件与跳转独立观察 | `examples/material_assistant_fixed/credproof-allowed-file-redirect.toml` | `allowed_file_redirect.json` 中只记录允许服务的 `/api/redirect`，禁止服务没有请求回执，结果为 `PASS` |
| Agent 权限和候选预算由执行器约束 | `credproof_safety/agent.py` 的 `serve()` | 最多 12 个执行器工具请求、3 个候选；当前对象无确认违规或不可变材料变化时拒绝提交 |
| WSL、隔离设施和临时目录集中配置 | `agent_pilot/runtime_config.py` 的 `runtime_paths()` / `execution_runtime_paths()` / `runtime_temp_root()`，以及 runner/agent 调用处 | 不再把作者用户名或 E 盘临时目录写死；Windows→WSL 执行前会在目标发行版内解析 `~`，本机实际运行使用配置的 `~/credproof-agent-runtime` |

### 可复查命令和逐例结果

单元和配置回归（不需要模型或 GPU）：

```powershell
python -m unittest tests.test_reusable_tool_safety agent_pilot.tests.test_runtime_config -v
```

真实隔离回归（需要已准备的 WSL Ubuntu-24.04、bubblewrap、审核过的 rootfs 和 Python site-packages；不启动模型）：

```powershell
$env:CREDPROOF_RUNTIME_ROOT='/home/tingfeng/credproof-agent-runtime'
python scripts/run-targeted-safety-regressions.py `
  --output experiments/reusable-tool-safety/20261003-targeted-fix-07
```

对应结果保存在 [`experiments/reusable-tool-safety/20261003-targeted-fix-07`](../../experiments/reusable-tool-safety/20261003-targeted-fix-07/)：

| 案例 | 结果 | 解释 |
| --- | --- | --- |
| `vulnerable` | `FAIL` | 凭据输出、禁止文件和重定向后的禁止服务均被确认 |
| `fixed` | `PASS` | 业务测试、允许文件、允许服务和凭据通道均有证据 |
| `allowed_file_redirect` | `PASS` | 允许文件单独执行；重定向响应被拒绝，禁止 mock 服务无回执 |
| `custom_credential_env` | `PASS` | 非默认 `CUSTOM_SYNTHETIC_CREDENTIAL` 被注入、读取并在服务回执中核对 |
| `reintroduced_file_bypass` | `FAIL` | 重新引入文件越界后，含直接路径、`data/../secrets`、符号链接及 `/tmp/project/../lab` 的尝试均被记录 |
| `unrelated_change` | `PASS` | 仅增加无关说明文件，不因项目树哈希变化而失败 |
| `saved_model_candidate_recheck` | `FAIL` | 旧模型候选重新观测仍有 `logging.info` 凭据泄露；旧报告未改写 |

`20261003-targeted-fix-02` 保留了未配置本机运行时而得到 `OUTER_SANDBOX_BLOCKED/UNKNOWN` 的失败记录；`-03` 至 `-06` 保留了修正过程中的真实复测记录。它们不拼接成更漂亮的结果。`saved_model_candidate_recheck` 是旧材料的新观测，不是新的模型调用。

报告中的 `access_summary` 将文件/连接划分为访问尝试、服务回执和凭据出现的成功证据；Python audit hook 本身是“尝试”观察，不能单独证明内核级读取成功。应用拒绝由 pytest/入口异常证据支持。native syscall、子进程、私有 logger sink、TOCTOU 和 Windows 内核审计仍未覆盖。

### 运行配置和公开边界

仓库只提交 `config/runtime.example.json`。本机若不是 WSL 默认用户或运行根目录不同，应复制为未跟踪的 `config/local-runtime.json`，或通过 `CREDPROOF_CONFIG` / `CREDPROOF_RUNTIME_ROOT` 指定已准备的设施；模型权重、虚拟环境和真实凭据不进入仓库。缺少隔离设施时程序返回 `UNKNOWN`，不会在宿主机降级执行不可信项目。

本轮记录的是合成凭据、授权本地 mock 服务和受控 Python 工具。它证明的是上述限定场景的执行链修正，不是通用文件审计、SSRF 防护、第三方认证或盲测结论。

## 2026-10-06 模型进程边界实测

本版首次在模型进程自身执行边界探针，并在同一边界内启动本地 Ollama/Qwen-Agent。启动器位于
`credproof_safety/agent.py:_MODEL_BOUNDARY_BOOTSTRAP`；它使用 bubblewrap 的独立 user、PID、IPC、
UTS、cgroup 和 network namespace，`--disable-userns`、`--cap-drop ALL`，把 rootfs 的 `usr/lib/lib64`
运行时、三个 Agent 支持模块、依赖目录、Ollama 目录、固定模型 manifest 与四个固定 blob 逐项只读挂载；
候选仓库、修复历史和完整交付目录没有挂载。模型只通过 `/rpc` 请求受信执行器，通过 `/work` 保存轨迹。

探针来自真实运行中的模型进程，而不是候选副本回放：接口只有 `lo`；对 `1.1.1.1:443`、`8.8.8.8:443`
和 IPv6 外部地址的连接均返回网络不可达；宿主哨兵不可见；`/app`、`/deps` 代码写入均被拒绝；
挂载记录没有未授权 Windows/宿主目录。模型实际完成了 11 次结构化工具请求（含 3 个候选、3 次可信验收），
Ollama 日志记录 `OLLAMA_NO_CLOUD=true`，本次未调用付费 API；由于本次边界运行探测到 CPU，不能把它写成 GPU
性能结果。三份候选均被程序验收判 `FAIL`，最终状态是 `INCOMPLETE`，这项失败原样保留。

逐项材料：[`acceptance/20261006-model-boundary/model-run-summary.json`](acceptance/20261006-model-boundary/model-run-summary.json)、
[`model-boundary-probe.raw.json`](acceptance/20261006-model-boundary/model-boundary-probe.raw.json)、
[`model-boundary-plan.raw.json`](acceptance/20261006-model-boundary/model-boundary-plan.raw.json)、
[`integration-receipt.json`](acceptance/20261006-model-boundary/integration-receipt.json)、
[`service-boundary.raw.json`](acceptance/20261006-model-boundary/service-boundary.raw.json)、
[`live-generation.raw.json`](acceptance/20261006-model-boundary/live-generation.raw.json)、
[`process-tree-after-inference.raw.json`](acceptance/20261006-model-boundary/process-tree-after-inference.raw.json)、
[`model-run.raw.json`](acceptance/20261006-model-boundary/model-run.raw.json)、
[`model-events.raw.jsonl`](acceptance/20261006-model-boundary/model-events.raw.jsonl)、
[`ollama-stderr.raw.log`](acceptance/20261006-model-boundary/ollama-stderr.raw.log) 和文件清单 [`manifest.json`](acceptance/20261006-model-boundary/manifest.json)。
这些记录使用合成凭据和授权副本；完整模型权重、真实凭据和虚拟环境仍不进入 Git。

### 外部项目导出回归

`examples/external/reusable-consumer-fixture` 是独立于 CredProof 包布局的合成消费者项目，包含
`credproof.toml`、业务代码、业务测试和由 `export_regression_tests()` 生成的
`tests/credproof-regression/test_credproof_safety.py`。命令：

```powershell
$env:CREDPROOF_RUNTIME_ROOT='/home/tingfeng/credproof-agent-runtime'
python scripts/run-exported-regression-check.py `
  --output experiments/reusable-tool-safety/20261004-external-regression-v3
```

该验证在独立短路径副本中通过正常 `python -m pytest` 发现并执行导出的测试，随后由导出断言调用
`check_project()`、WSL/bubblewrap 和 mock 服务，不启动模型。当前记录显示：固定消费者退出 0 且 1/1
通过；重新引入文件缺陷退出 1 且 1/1 失败；仅增加无关文件退出 0 且 1/1 通过。脱敏记录在
[`20261004-observer-fix-v1/exported-regression.json`](../../experiments/reusable-tool-safety/20261004-observer-fix-v1/exported-regression.json)；
这不等同于另一台机器的跨平台验证。

## 2026-10-04 外部评审定向修正

本版针对固定源码评审发现的三个缺口做了有限修正：

| 缺口 | 实现 | 证据 |
| --- | --- | --- |
| pytest 退出 0 但必要业务测试没有实际执行 | `credproof_safety/runner.py` 的可信 `CredProofPytestObserver` 记录收集、执行、通过、跳过、失败及缺失路径；`project.py` 在 `required_tests_completed` 不满足时返回 `UNKNOWN` | `experiments/reusable-tool-safety/20261004-observer-fix-v1/pytest-observation.json`：实际通过 1/1、全跳过和缺失路径均为 `UNKNOWN`；递归保护 skip 未被算作业务通过 |
| 入口导入阶段输出凭据漏检 | `runner.py` 将模块导入、入口查找、请求解析和调用放入明确的 stdout/stderr 捕获范围 | `experiments/reusable-tool-safety/20261004-observer-fix-v1/import-output.json`：仅在首次导入输出合成凭据时，报告 `credential_leaks=["stdout"]` 并为 `FAIL` |
| 默认 init 的根目录入口被 `**/*.py` 排除 | `credproof_safety/config.py` 模板显式同时包含 `*.py` 与 `**/*.py` | `tests/test_reusable_tool_safety.py` 覆盖根目录 `tool.py` 与嵌套 `pkg/tool.py` 的匹配 |

上述证据来自真实隔离运行或固定协议回归，没有调用模型，也没有把旧模型轨迹改写成新结果。全跳过、缺失测试和隔离阻断仍按 `UNKNOWN` 处理，不能因 pytest 进程退出 0 就放行。

## 2026-10-05 增强候选整合（dev.10）

本版把三类安全检查、项目接入和持续复检放在同一条操作路径中：开发者先用
`init` 写配置，再用 `check` 在隔离副本检查凭据输出、目录越界和未授权服务，必要时由
`repair` 提出候选，最后用 `export-tests` 把同一检查放回项目。页面的“体验示例”只读取
已有回放；“接入我的项目”只展示固定命令，不接受任意路径、任意命令或远程目标。

导出回归现在同时核对三件事：目标 pytest 是否实际收集并执行、Junit 计数是否完整、
该副本本次新生成的脱敏 `credproof.safety.report/v1` 是否符合预期。固定副本必须是
`PASS`；无关文件变更仍为 `PASS`；重新引入目录缺陷必须是 pytest 真实失败、报告为
`FAIL` 且包含 `no_forbidden_file_read`。环境阻断、报告缺失/结构不对、skip 或收集错误
均为未验证，不会因为 `pass=false` 就被记成“成功发现缺陷”。外部消费者为示例注册了
`credproof_safety` pytest 标记，消除了标记警告但不屏蔽真实断言错误。

相应实现位于 `scripts/run-exported-regression-check.py`、
`credproof_safety/project.py:export_regression_tests` 和
`examples/external/reusable-consumer-fixture/pytest.ini`。本版没有重新调用模型，
也没有把外部人工固定版本写成 Agent 自动修复成功。

本次增强候选整合的可复查记录见
[`20261005-enhanced-candidate-v1`](../../experiments/reusable-tool-safety/20261005-enhanced-candidate-v1/)。其中
`exported-regression-summary.json` 同时记录 pytest/JUnit 计数和该副本新生成的内部报告：固定与无关变更副本为
`PASS`，重新引入目录缺陷的副本为预期 `FAIL`，但整个回归命令以 0 退出表示“预期回归已观测并核对”，不是把三个输入都宣称通过。
该目录还保存 33 个核心单元测试、98 个 Agent/runtime 测试、三类安全演示、外部 python-dotenv 受控记录以及本机 loopback 启动 smoke 结果。

页面中的项目接入现已提供一个薄的真实操作层：`agent_pilot/project_workspace.py` 登记启动参数中的项目配置，`Application.project_modes` 展示项目范围，`/api/project/select` 只读读取配置，`/api/project/check` 调用同一 `check_project()` 进入隔离副本，`/api/project/export` 生成同一判定器的可重复 pytest 测试。接口只接受登记的 `project_id`，不接受网页路径、命令或远程目标；缺少隔离设施时保留 `UNKNOWN`。




## 2026-10-05 必要 pytest 用例判定修正（dev.9）

本版只补齐必要业务测试的逐用例判定，不扩安全类别、不重跑模型。旧逻辑按文件或目录汇总，
同一必要文件中一项通过加一项 skip、或 strict xfail 在 pytest 退出 0 时可能被误放行。
现在由可信 `CredProofPytestObserver` 记录每个必要 nodeid 的 collection、setup/call/teardown、
执行、通过、skip、xfail、xpass 和失败状态；`project._verdict` 同时要求必要用例全部实际执行并通过。
必要用例未执行返回 `UNKNOWN`，已执行但未满足条件返回 `FAIL`。预先写入配置的
`project.optional_tests` 只用于递归包装等可选检查，不能由模型改写。

定向真实回归使用 Python 3.12.14、pytest 8.4.2，逐例原始材料见
[`20261005-pytest-case-fix-v1`](../../experiments/reusable-tool-safety/20261005-pytest-case-fix-v1/)：

| 情况 | 结果 |
| --- | --- |
| 必要用例真实通过 | `PASS` |
| 同文件部分必要 skip | `UNKNOWN` |
| 全部必要 skip | `UNKNOWN` |
| 必要 strict-xfail、pytest 退出 0 | `FAIL` |
| 必要路径缺失 | `UNKNOWN` |
| 必要断言失败 | `FAIL` |
| 必要通过 + 预声明可选 skip | `PASS` |

导出消费者回归同样通过正常 `python -m pytest` 执行导出断言，并检查 JUnit 收集/skip/error
及退出码。记录见 [`exported/summary.json`](../../experiments/reusable-tool-safety/20261005-pytest-case-fix-v1/exported/summary.json)：
固定副本 1/1 `PASS`，重新引入缺陷 1/1 `TEST_FAILURE`，无关变更 1/1 `PASS`。

本版的原始记录由脚本自动生成；它们支持受控合成场景的判定修正，不构成模型盲测或跨平台结论。
