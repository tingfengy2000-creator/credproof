# CredProof reusable-tool-safety（0.3.0-dev.1）

本开发分支把 CredProof 的受控凭据验收扩展到两类实际工具行为：越过配置目录
读取文件、以及访问未授权的 HTTP 服务。它面向有源码和授权的小型 Python 工具，
使用一个版本化的 `credproof.toml` 和已有 pytest 测试。原初赛候选版仍在旧分支
和旧提交中保留，本页只记录新开发分支。

## 已实现的共同入口

源码包可用 `python -m pip install .` 安装；本轮在独立临时 Python 3.14 venv 中用
`setuptools` 构建 wheel `credproof_safety-0.3.0.dev1-py3-none-any.whl`，源码目录
本身也可直接运行 `python -m credproof_safety`。模型权重和 Ollama 不随 wheel 进入
安装包。

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
环境中的 `127.0.0.1` 动态 HTTP mock；不满足该范围的配置会被拒绝，避免把未实现的
网络规则写成已验证。规则由配置和程序验收器固定，模型不能修改规则、删除测试
或自行宣布通过。

## 真实受控结果

`scripts/run-reusable-safety-demo.py` 在三个 disposable 副本中运行同一流程：

| 副本 | 实际结果 | 含义 |
| --- | --- | --- |
| `examples/material_assistant` | `FAIL` | 真实读取禁止文件、跟随重定向到禁止 mock 服务、返回凭据 |
| `examples/material_assistant_fixed` | `PASS` | 业务 pytest 通过，允许文件和允许服务仍可用，凭据未输出 |
| fixed 副本重新引入文件检查缺陷 | `FAIL` | 同类回归重新被观测到 |

每次报告都区分 `ACTUAL_VIOLATION`、`OUTER_SANDBOX_BLOCKED` 和 `INCOMPLETE`。
目前的观测面是 Python `open`/`socket.connect` audit 事件及独立 mock HTTP 服务的
请求回执；原生扩展直接系统调用、TOCTOU、Windows 内核审计和完整 DNS/SSRF 语义
仍列为未覆盖。项目自身的外部符号链接会被拒绝；实验目录中的越界符号链接仅在
宿主能够创建时纳入实验。`read then discard` 仍算读取违规。

## 外部项目接入

`examples/external/python-dotenv-v1.2.2` 保留了上游 `src/dotenv`、`tests/test_main.py`、
`tests/conftest.py`、`LICENSE`、`pyproject.toml` 和 `README.md`，固定提交为
`36004e0e34be7665ff2b11a8a4005144f76f176d`，BSD-3-Clause。原始上游测试在隔离副本中
得到 **114 passed**。`credproof_entry.py` 是明确标注的人工注入目录读取缺陷，
不是上游漏洞或 CVE；`credproof_entry_fixed.py` 仅增加授权目录约束并保留 dotenv
解析。对应的 before/after 命令见 `README-credproof.md` 和
`scripts/run-external-dotenv-case.py`。

本轮固定记录位于 `experiments/reusable-tool-safety/20261003-final/`：资料助手为
`vulnerable=FAIL`、`fixed=PASS`、重新引入文件缺陷再次 `FAIL`；外部
python-dotenv 为人工注入版本 `FAIL`、修复适配 `PASS`，上游 pytest 为 114 passed。
本地模型的成功与不完整轨迹分别位于 `agent-runs/agent-repair-success` 和
`agent-runs/agent-repair-rpc3`，两者不合并为总体成功率。
WSL、bubblewrap、rootfs、Q4_K_M 模型和完整 Ollama digest 记录在同目录的
`runtime-receipt.json`；权重不进入 Git。

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
仓库外，且需要既有本地 Ollama/Qwen 运行时。

## 当前边界

只承诺声明环境中的小型 Python 项目、一个配置入口和受控 pytest 测试；不支持任意
Shell、自动安装脚本、真实凭据、公网目标、云端撤销、多语言或通用 SSRF 证明。开发
者仍需人工确认允许目录、服务、入口、必要业务测试和修改范围。Windows 本机原始
路径、Windows 内核审计和跨机器部署尚未作全平台承诺。
