## 清洁安装与需求验收（dev18）

本版先完成清洁安装链路和可复核需求表，再决定是否交接 5060。入口文件是 [`requirements-acceptance.md`](requirements-acceptance.md) 与机器可读的 [`requirements-acceptance.json`](requirements-acceptance.json)。

- 清洁安装证据：[`acceptance/20261006-final/`](acceptance/20261006-final/)；包括 wheel、site-packages 导入来源、CLI before/fixed、浏览器实际操作、导出消费者 pytest/JUnit 和环境预检。
- 清洁安装发现的 wheel 静态资源缺口已在 `pyproject.toml` 修复，细节见 [`packaging-gap.md`](packaging-gap.md)。
- 无模型项目检查与导出记录见 [`page-flow.md`](page-flow.md)；模型现场入口的真实 HTTP 记录见 [`acceptance/20261006-page-live-boundary/`](acceptance/20261006-page-live-boundary/)。
- dev18 wheel、site-packages 导入和清洁安装现场入口收据见 [`acceptance/20261006-live-correction/`](acceptance/20261006-live-correction/)。旧 dev16/dev17 收据仍原样保留。
- 当前状态：程序检查、导出链以及模型边界运行均有可读证据；最新上下文适配任务按真实请求预算以 `INCOMPLETE` 结束，不能写成自动修复成功。
- 本轮新增 [`acceptance/20261006-live-correction/`](acceptance/20261006-live-correction/)：保存的现场候选按新 `project-bundle/v1` 导出并在新目录复检，真实结果仍为 `FAIL`。页面批次实际接受 1 份候选、验收 1 次；清洁 wheel 批次接受 0 份候选，二者未合并统计。

# CredProof reusable-tool-safety（0.3.0-dev.22）

本开发分支把 CredProof 的受控凭据验收扩展到两类实际工具行为：越过配置目录
读取文件、以及访问未授权的 HTTP 服务。它面向有源码和授权的小型 Python 工具，
使用一个版本化的 `credproof.toml` 和已有 pytest 测试。原初赛候选版仍在旧分支
和旧提交中保留，本页只记录新开发分支。

## dev18 定向收尾：项目 bundle 身份与可信启动器

本版在不重跑模型的前提下关闭两类材料归属问题。`credproof_safety/project_bundle.py:export_project_bundle`
在首次导出前同时核对候选副本的 `project_tree_sha256`、实际 `credproof.toml`、入口文件、必要测试
和 `final_validation`；入口只允许显式的 LF/CRLF 语义比对，候选配置或测试变化不会沿用旧报告。
复制到 bundle 后还会再次核对树摘要。`recheck_project_bundle` 同时接受旧的
`project-bundle/v1` 和本次派生的 `project-public-bundle/v1`，并拒绝清单路径越界。

公开取件材料 [`public-project-bundle-dev17/`](acceptance/20261006-live-correction/public-project-bundle-dev17/)
由固定提交 `8c66d7916cfe406aa2d1b6f3d6e9f49a977d5564` 的 Git blob 重新取得，按 Git 字节发布，
没有使用 Windows checkout 的换行转换。清单中的 `project/tool.py` 为
`fbdcf41db9834b3507326f9f15846e41274a563b58b5e27fbddab13e8c6570a7`，旧本地 CRLF 清单仍在
`new-project-bundle/` 中原样保留；`publication.json` 明确记录来源提交、来源验收树和公开树的关系。
在当前隔离环境执行 [`public-project-recheck-dev17.json`](acceptance/20261006-live-correction/public-project-recheck-dev17.json)
得到真实 `FAIL`（pytest 3 收集/执行，2 通过、1 失败），不是把缺材料或 UNKNOWN 当成检出。
首次导出协议的无模型回归见 [`binding-regression-dev18.json`](acceptance/20261006-live-correction/binding-regression-dev18.json)：
正常导出为 `EXPORTED`，候选/配置/必要测试在首次导出前变化均被拒绝，导出后变化返回 `UNKNOWN` 且旧报告不适用。

页面子进程不再扫描 `_runs/clean-install-dev16/dev17` 等临时目录。`agent_pilot/web.py:launch_command`
只接受环境变量 `CREDPROOF_INSTALLED_PYTHON` 或集中配置 `config/local-runtime.json` 的
`program_python`，路径不存在会明确报错，不回退旧包；始终使用 `python -I -m credproof_safety.web_repair`。
无模型的解释器选择回归见 `agent_pilot/tests/test_runtime_config.py`。模型修复成功仍未验证，状态继续为
`NOT_READY_FOR_HANDOFF`。
新安装位置的 `python -I -m credproof_safety.web_repair --origin-only` 记录见
[`installed-origin-dev18.json`](acceptance/20261006-live-correction/installed-origin-dev18.json)：
wheel 为 `credproof_safety-0.3.0.dev18-py3-none-any.whl`，子进程的 `web_repair.py` 和 `agent.py`
均来自该 venv 的 `site-packages`，工作目录与仓库分离，未启动模型。

## 已实现的共同入口

源码包可用 `python -m pip install .` 安装；本轮在独立 Python 3.12 venv 中用
`setuptools` 构建 wheel `credproof_safety-0.3.0.dev18-py3-none-any.whl`，源码目录
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
这仍不是公平盲测或通用隔离证明：模型运行只覆盖一个授权合成项目；页面新现场记录实际接受一份候选并判 `FAIL`，
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

仓库只提交 `config/runtime.example.json`。本机若不是 WSL 默认用户或运行根目录不同，应复制为未跟踪的 `config/local-runtime.json`；现场页面还必须在该文件增加已核验安装解释器的绝对路径 `"program_python": "C:\\...\\python.exe"`，或通过 `CREDPROOF_INSTALLED_PYTHON` 明确指定。这两个入口都只接受存在的安装解释器，失效时直接报错，不会从历史 `_runs` 静默回退。也可通过 `CREDPROOF_CONFIG` / `CREDPROOF_RUNTIME_ROOT` 指定已准备的设施；模型权重、虚拟环境和真实凭据不进入仓库。缺少隔离设施时程序返回 `UNKNOWN`，不会在宿主机降级执行不可信项目。

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


## 2026-10-07 受限 Agent 效果复测（历史 dev19 记录）

对登记任务 p01 只进行了一次冻结的有限模型运行。新的 get_evidence 已列出真实入口和业务测试，但模型仍有两次猜路径，随后在提交候选前触发一次 FAIL 验收，并在第4次请求达到120秒单请求超时；独立统计为4次模型尝试、3份usage、6次工具请求、0个接受候选、1次FAIL验收。没有模型修复PASS、候选导出或新目录复检，状态继续为 `NOT_READY_FOR_HANDOFF`。完整脱敏轨迹见 [`acceptance/20261007-agent-effect/`](acceptance/20261007-agent-effect/)。

## 2026-10-07 顺序修正与正式 p01 效果

本轮将第一个模型请求改为携带受控副本生成的真实文件索引和规则上下文，并由执行器实施证据→读取→提交→验收的阶段门槛。`verify_patch` 在没有被接受候选时返回 `NO_ACCEPTED_CANDIDATE`，不会把原代码检查记作候选验收。旧轨迹的更正说明和原始材料见 [`acceptance/20261007-agent-sequencing/formal-p01/evidence/README.md`](acceptance/20261007-agent-sequencing/formal-p01/evidence/README.md)。

在同一模型与隔离边界下，正式 `assistant-original/p01` 实际使用 `CUDA0 / NVIDIA GeForce RTX 5090 / 31.8 GiB`。本次运行是 6 次模型请求、6 份 usage、7 次工具请求、2 个接受候选和 2 次验收：候选 1 因凭据仍出现在不允许输出通道而 FAIL，候选 2 通过安全与业务检查；同一候选完成 project-bundle 导出，并在新目录无模型复检 PASS。结果摘要、第一请求、工具轨迹、候选和复检材料位于 [`acceptance/20261007-agent-sequencing/`](acceptance/20261007-agent-sequencing/)。

此前的 4/3/6/0/1 数字仍是历史页面批次，未与本次正式运行合并。两次 boundary-only 诊断阻断分别保留为诊断记录；一次未传递 boundary-only 标志的运行已按实际内容重分类为正式 p01，而不是短探针。


## 当前 dev21：返回值与跳转场景已补齐，模型修复仍未成立

本轮把原来未执行的两类条件写进同一份项目配置和可信检查：允许文件+允许服务的实际返回必须不含合成凭据；允许文件+`/api/redirect` 必须记录允许服务观测并得到声明的 `HTTPError`，没有请求证据为 `UNKNOWN`，实际收到禁止服务为 `FAIL`。原始版本与保存的 candidate-02 均按新规则真实 `FAIL`；candidate-02 的正常返回仍含合成凭据，并在跳转后收到禁止服务 `/secret`。逐场景 JSON 在 [`acceptance/20261007-return-redirect/`](acceptance/20261007-return-redirect/)。

随后只执行一次冻结的正式本地模型任务。模型边界探针为 CUDA0/RTX 5090、白名单挂载和 loopback-only 私有网络；模型在 `get_evidence` 后读取了两个声明文件，但执行器在第 1 次模型请求后因保守输入预算将被超出而停止，未提交候选、未验收、未导出。它不是修复成功，也不是超时；完整请求、响应和边界收据见 [`formal-p01-model-result.json`](acceptance/20261007-return-redirect/formal-p01-model-result.json)、[`formal-p01-model-result-artifacts/`](acceptance/20261007-return-redirect/formal-p01-model-result-artifacts/) 和 [`formal-p01-model-summary.json`](acceptance/20261007-return-redirect/formal-p01-model-summary.json)。

保存 candidate-02 的当前规则 bundle 已在新目录无模型复检为 `FAIL`；它只用于验证公开取件与失败依据，不充当 Agent 成功。旧 dev20 Git 字节派生包保持为旧单场景历史材料。当前状态为 `NOT_READY_FOR_HANDOFF`，5060 尚未启动。


### 修订失败候选的公开取件核对

保存的 candidate-02 派生公开 bundle 位于 [`public-saved-candidate02-bundle-dev21/`](acceptance/20261007-return-redirect/public-saved-candidate02-bundle-dev21/)，对应 [`public-saved-candidate02-recheck-dev21.json`](acceptance/20261007-return-redirect/public-saved-candidate02-recheck-dev21.json)。该 bundle 从固定 Git 提交 `6aeebcf` 的 Git blob 取得；`project/tool.py` 为 1808 bytes、LF、SHA-256 `f7b017b6d8789dddc9231d89a3b0185713be9f869620262602e369b0b310a9a9`。字节收据 [`public-saved-candidate02-byte-verification-dev21.json`](acceptance/20261007-return-redirect/public-saved-candidate02-byte-verification-dev21.json) 的清单和 Git 源材料匹配均为 true。公开 bundle 的新目录复检仍为 `FAIL`，因为它是保存的失败候选；这项材料证明公开取件与复检链路，不证明模型修复成功。

## 当前 dev22：上下文预算适配后的唯一正式运行

本轮只针对已登记的 `assistant-original/p01` 任务整理消息。首请求改为入口、有限文件索引、修改范围和规则摘要；`get_evidence` 返回有界结构化证据，完整报告仍独立保存。提交/验收阶段把内部历史压缩为基础任务加最新依赖工具对，执行器保留完整原始轨迹。协议预检使用客户端实际序列化和工具 schema，首请求、证据加两份源码、候选失败反馈三个阶段均在 16K 上下文限制内；记录见 [`acceptance/20261007-return-redirect/20261007-context-budget-preflight.json`](acceptance/20261007-return-redirect/20261007-context-budget-preflight.json) 和 [`acceptance/20261007-return-redirect/context-budget-pilot/README.md`](acceptance/20261007-return-redirect/context-budget-pilot/README.md)。预检没有调用模型，也不把字节值当作服务 token 用量。

随后在源码提交 `e6507f36b93a0a3168717cf7f09f439b57786132` 对应的同一 5090、同一模型和既定隔离边界中只运行一次正式任务。实际结果是 12 次模型请求、12 份 usage、15 次工具请求尝试，其中前 12 次由执行器处理、后 3 次因工具请求上限拒绝；接受 2 份候选。候选 1 被真实验收为 `FAIL`，候选 2 已保存但未验收；任务以 `INCOMPLETE` 和 `Model request budget exhausted` 结束。运行期间没有再次出现 input-budget 超限事件，也没有候选获得可信 `PASS`，所以没有导出或新目录无模型复检。脱敏后的逐请求轨迹、候选和边界记录位于 [`acceptance/20261007-return-redirect/context-budget-pilot/public-evidence/`](acceptance/20261007-return-redirect/context-budget-pilot/public-evidence/)，汇总见 [`run-summary.json`](acceptance/20261007-return-redirect/context-budget-pilot/public-evidence/run-summary.json)。

这次运行证明了消息组织和预算保护可以让模型继续工作到候选阶段，但没有证明当前模型修复效果。候选 2 不是 PASS，也不能与旧 h03、人工修复或历史 bundle 拼接。当前状态仍为 `NOT_READY_FOR_HANDOFF`，5060 尚未启动。


## 当前 dev23 评审入口

本轮上下文保真、候选自动验收和工具额度停止的代码在 `agent_pilot/model_client.py`、`credproof_safety/agent.py`；真实 v3 记录入口为 [`acceptance/20261007-return-redirect/context-budget-pilot-v3/`](acceptance/20261007-return-redirect/context-budget-pilot-v3/)。当前模型任务仍无可信 PASS，状态为 `NOT_READY_FOR_HANDOFF`。

## dev24：压缩后最新读取保真与一次有限复测

本轮只修复消息压缩在已有候选之后丢失最新 `read_code(tool.py)` 对、造成模型请求原地重复的问题。`agent_pilot/model_client.py:compact_messages_for_budget` 现在按真实 `function_id` 保留最新读取的完整调用/返回对，保留当前候选源码、必要测试、程序自动验收失败和主机最新 `executor_state`；只有与当前对象脱离的旧入口读取可以去重。旧的 `REJECTED`、`ERROR`、`UNKNOWN` 和失败原因不改写。候选提交后的验收仍由执行器自动调用，重复同一对象/读取状态达到阈值时由 `credproof_safety/agent.py:_read_progress_update` 产生明确的 `no_progress_same_read`，模型侧结束为 `STOPPED_NO_PROGRESS`。重复的 `get_evidence` 在已有读取或候选后也会被执行器拒绝为 `evidence_already_current`，避免再次占用上下文。

先用 v3 原始请求、响应和工具结果做了不调用模型的真实消息重放。`payload-before.json` 是修复前保存的第5次请求，它没有最新入口读取；`payload-after-read-05.json` 和 `payload-after-read-12.json` 由当前转换器和真实 v3 工具结果生成。8个连续读取均保留最新调用ID与配对返回、当前 `tool.py` 正文、候选1的 `FAIL` 验收和 `tool_calls_used` 5→12 的最新状态；请求摘要不再相同，所有工具ID成对。该重放只验证协议，不执行候选，也不是模型修复成功。预算预检使用相同客户端序列化和工具定义，首请求、两份源码、自动验收失败以及失败后重新读取四个阶段均 `within_declared_budget=true`，最高保守上界 14,583/14,848。

随后在源码提交 `502072a1e20459bbf0e474ce0630c6cc22b6a842` 上、同一 `assistant-original/p01`、qwen3-coder:30b、5090 CUDA0 和既有 bubblewrap 边界内只运行一次正式任务。实际为 **5次模型请求、5份服务usage、6次工具请求、1个接受候选、1次程序自动验收**；候选1仍为 `FAIL`（凭据仍出现在返回值，正常/跳转边界及必要业务未满足），没有可信 `PASS`、导出或新目录复检。模型在第5次请求后再次请求已完成的 `get_evidence`，后续请求被保守输入预算保护拒绝；这次失败原样保留，没有用重试覆盖。Ollama日志确认本次使用 `CUDA0 / NVIDIA GeForce RTX 5090`，模型边界探针仍为白名单挂载和 loopback-only 私有网络，付费 API 为 false。

为避免相同阶段再次循环，当前源码随后在 `16498c6` 增加了 `evidence_already_current` 阶段拒绝；这项修正只做了协议/单元回归，没有再次调用模型。完整原始运行留在本机评审目录；公开脱敏证据在 [`acceptance/20261007-return-redirect/context-budget-pilot-v4/public-evidence/`](acceptance/20261007-return-redirect/context-budget-pilot-v4/public-evidence/)，包括真实请求/响应、预算、候选和边界收据。协议重放及摘要见 [`context-budget-pilot-v4/replay-summary.json`](acceptance/20261007-return-redirect/context-budget-pilot-v4/replay-summary.json)。本轮仍为 `NOT_READY_FOR_HANDOFF`，5060 尚未启动。
