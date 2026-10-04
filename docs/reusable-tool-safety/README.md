# CredProof reusable-tool-safety（0.3.0-dev.7）

本开发分支把 CredProof 的受控凭据验收扩展到两类实际工具行为：越过配置目录
读取文件、以及访问未授权的 HTTP 服务。它面向有源码和授权的小型 Python 工具，
使用一个版本化的 `credproof.toml` 和已有 pytest 测试。原初赛候选版仍在旧分支
和旧提交中保留，本页只记录新开发分支。

## 已实现的共同入口

源码包可用 `python -m pip install .` 安装；本轮在独立临时 Python 3.14 venv 中用
`setuptools` 构建 wheel `credproof_safety-0.3.0.dev7-py3-none-any.whl`，源码目录
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
解析为 WSL 内的绝对路径，真实完成了 117 个上游 pytest 测试（每个副本退出码 0），
并取得上述四项判定。逐例记录保存在
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
仓库外，且需要既有本地 Ollama/Qwen 运行时。候选的检查由 bubblewrap 副本完成；
当前模型进程本身只验证了 WSL 独立网络命名空间，尚未完成只挂载白名单的文件系统隔离。
因此模型轨迹不能被描述为公平盲测：继续运行时不得把仓库里的测试标签、历史结果或
参考补丁交给模型，正式盲测需先补这层隔离。

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

### 外部项目导出回归

`examples/external/reusable-consumer-fixture` 是独立于 CredProof 包布局的合成消费者项目，包含
`credproof.toml`、业务代码、业务测试和由 `export_regression_tests()` 生成的
`tests/credproof-regression/test_credproof_safety.py`。命令：

```powershell
$env:CREDPROOF_RUNTIME_ROOT='/home/tingfeng/credproof-agent-runtime'
python scripts/run-exported-regression-check.py `
  --output experiments/reusable-tool-safety/20261003-external-regression-02
```

该验证直接调用导出的 pytest 断言函数，因为当前 Windows 环境没有安装 host pytest；它仍真实调用
`check_project()`、WSL/bubblewrap 和 mock 服务，不启动模型。固定消费者通过，临时重新引入文件缺陷失败，
仅增加无关文件仍通过。记录在 [`experiments/reusable-tool-safety/20261003-external-regression-02`](../../experiments/reusable-tool-safety/20261003-external-regression-02/)；这不等同于另一台机器的跨平台验证。


