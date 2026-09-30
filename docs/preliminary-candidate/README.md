# 密证 CredProof：初赛候选阅读与运行入口

**作品名称：密证 CredProof——面向 AI 工具的凭据泄露验证与受控修复系统。候选版本：`0.2.0-preliminary.2`。**

系统结合本地大模型补丁生成与程序控制的安全验收，针对凭据泄露问题给出候选修复，并检查泄露是否消除、必要业务行为是否保持，支持材料导出与复检。

从作品首页开始，先了解三个特点和主机制，再依次查看 **h01 有限修复增量 → h03 失败候选与反馈调整 → h07 正常保留 → 材料复检**。精选案例展示真实过程，完整批次结果保留全部八例。本版更新展示与材料，未新增模型实验或案例集；已验证环境仍是 Windows + WSL，适用场景为已登记、已适配业务接口的受控 Python 工具。当前材料供初赛打磨，身份、声明及参赛规则仍待本人确认。

## 1. 先读这些材料

| 内容 | 入口 |
|---|---|
| 候选作品报告 | [PDF](credproof-manuscript-candidate.pdf)、[Word](credproof-manuscript-candidate.docx)、[可审阅正文](manuscript.md) |
| 摘要与一页说明 | [summary.md](summary.md) |
| 机制图 | [PNG](assets/mechanism.png)、[SVG](assets/mechanism.svg) |
| 三分钟讲解 | [demo-script.md](demo-script.md)：h01、h03、h07 均为真实历史回放 |
| 一页展示顺序、60 秒提纲与录屏分镜 | [presentation-guide.md](presentation-guide.md)：页面区域、点击顺序和关键话 |
| 本版展示与交付检查 | [presentation-checks.md](presentation-checks.md)：界面、叙事、材料与旧档保护 |
| 答辩准备 | [qa.md](qa.md) |
| 官方模板、匿名和待确认事项 | [template-requirements.md](template-requirements.md) |
| 报告构建与版式处理 | [build-instructions.md](build-instructions.md) |
| 上版固定预算发布检查（2026-09-29） | [checks.md](checks.md)：一次 h01 现场任务、三份独立复检材料、对象变化拒绝复用 |
| 上版材料完整性检查（2026-09-29） | [命令及退出码](checks/bundle-integrity/20260929T135515Z/command-log.json)、[完整材料复检](checks/bundle-integrity/20260929T135515Z/intact-recheck.json)、[缺可选轨迹复检](checks/bundle-integrity/20260929T135515Z/missing-optional-trace-recheck.json) |

Word/PDF 是候选文稿产物；最终提交仍需队伍确认身份与贡献、提交日期、匿名属性、文件命名和大小。内部研发记录包含机器路径及历史来源，不应直接把整个研发包当成匿名参赛报告。

## 2. 三种操作需要不同环境

| 操作 | 实际发生什么 | 必要条件 |
|---|---|---|
| 历史演示 REPLAY | 读取既有真实记录，在 `runs/demo-replay` 建立展示副本；不产生新模型结果 | 普通 Python、包内历史记录、可写的 `runs`；无 WSL/GPU 也可看回放 |
| 现场分析与修复 | 单独启动本地 Agent 和模型，生成新的候选、工具调用与验收记录 | 已准备的 WSL/Linux Python 依赖、本地 Ollama/模型、通过门禁的隔离设施；实际验证的机器有 RTX 5090 |
| 材料重新验收 | 重读当前副本和清单，运行固定 13 项检查 | 普通 Python 与已准备、通过探针的隔离设施；不需要 GPU、Qwen 或模型服务 |

“模型文件就绪”不表示模型已经推理成功；“当前对象 PASS”也不等于整个 Agent 任务完成。旧报告适用性、历史材料完整性和当前复检结果分别显示。

## 3. 从代码树根目录启动

本机已完成首次准备时，无需再次下载模型或重新 prepare。Windows PowerShell 在代码树根目录运行：

```powershell
python -m agent_pilot.launch --demo
```

打开 `http://127.0.0.1:8765/`；端口可用 `--port 8767` 改变。启动器只监听本机回环地址。`--demo` 装入 h01、h03、h07 三份历史，始终标为 **REPLAY**；关闭服务不会删除原始实验记录。它不是新推理，也不代表总体成功率。

点击“返回新任务”，选择已登记案例，再点击“开始分析与修复”才创建新推理。环境不就绪时现场操作受门禁阻断，回放页面仍可启动；模型超时、工具调用错误或预算耗尽必须保留真实失败/未完成状态。没有切换付费云模型的回退。

单独查看当前运行设施：

```powershell
python -m agent_pilot.preflight
```

退出 `0` 表示只读观察的 `ready=true`；退出 `2` 表示尚有条件不满足。该命令读取既有探针收据、身份摘要和模型文件，不下载、不启动模型、不重新探针、不执行候选。它分别给出 `isolation_ready`、`model_ready`、原因和观察范围。

预检会对小模型 blob 核对 SHA256，对大权重只核对存在性及声明尺寸，**不会每次重新完整哈希大权重**。本机 config 小 blob 存在“声明 539 字节、实际 542 字节，但 SHA256 匹配”的已知元数据差异，会显式显示警告；它不是被隐藏的推理成功证据。

## 4. 配置与首次准备

[默认示例](../../config/runtime.example.json)只有三个字段：

```json
{
  "wsl_distribution": "Ubuntu-24.04",
  "wsl_user": "",
  "runtime_root": "~/credproof-agent-runtime"
}
```

空用户名使用所选 WSL 发行版的默认用户；`~` 在 Linux 用户环境展开。需要调整时，把示例复制到本机的 `config/local-runtime.json` 并设置已准备的运行目录，或通过 `CREDPROOF_CONFIG` 指定配置文件路径。`CREDPROOF_RUNTIME_ROOT` 可显式覆盖 Linux 运行根目录；它接受 Linux 绝对路径或 `~/` 路径，不是 Windows 盘符路径。只改变配置不会生成设施或使无效探针变绿。

现场运行所需目录组织为：

```text
<runtime_root>/
  venv/bin/python
  ollama/bin/ollama
  models/manifests/registry.ollama.ai/library/qwen3-coder/30b
  models/blobs/...
  isolation/probe-receipt.json
  isolation/rootfs/...
  isolation/tools/usr/bin/bwrap
  isolation/seccomp.bpf
```

已验证组合是 Windows 11、WSL Ubuntu 24.04、Linux Python 3.12.3、Qwen-Agent 0.0.34、Ollama 0.34.4、`qwen3-coder:30b` Q4_K_M 和 RTX 5090；[原始环境记录](../local-agent/validation/environment.json)与[依赖锁](../../agent_pilot/requirements-lock.txt)可查。其他机器需要单独准备与验证，不承诺 CPU 现场推理速度、跨机器开箱即用或相同输出。

首次准备按以下已有资料完成，准备阶段和正式离线运行分开：

1. 在所选 WSL/Linux 用户的独立目录准备 Python venv，按 [framework.md](../local-agent/framework.md) 从官方 PyPI 安装锁定依赖。没有必要安装 RAG、GUI、code interpreter extras；Windows 展示进程不需要安装 Qwen。
2. 准备官方 Ollama 0.34.4 独立 Linux 文件和下述固定模型，[模型下载核验记录](../local-agent/validation/model-download.json)保存完整摘要。权重不随候选包分发，不从浮动标签的名字推定字节相同。
3. 按 [isolation.md](../local-agent/isolation.md) 准备、探测固定可信隔离设施。`prepare/probe` 是单独的显式操作；重新准备会关闭旧门禁，必须重新通过探针。缺隔离、缺收据或身份漂移时，候选不能在宿主直接执行。
4. 回到本代码树根目录运行预检，再由现场入口进行单独的新推理。现场服务和 Agent 使用隔离的本地回环网络，模型客户端固定连接 `127.0.0.1:11435`。

[download-model.py](../../agent_pilot/download-model.py) 已使用统一运行根目录配置；操作者仍须按其阶段条件准备目标目录和已固定的 manifest。[prepare-ollama.py](../../agent_pilot/prepare-ollama.py) 的 zstd 解包阶段使用 Python 3.14，随后在 WSL 解包到明确的新目录。这些工具不代替首次依赖、路径、权限与隔离验收，不构成跨机器一键安装保证。旧准备文档保留当时的本机路径，当前运行入口以上述配置为准。

固定模型身份如下；详细 blob 列表以下载核验 JSON 为准：

| 项目 | SHA256 |
|---|---|
| 模型 manifest | `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca` |
| Q4_K_M 主权重 blob | `1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a` |
| Ollama 0.34.4 官方 Linux 归档 | `c238986e61d40c0cc5f4a9b9e40b9eea104350b77efa34741fc134e105cb9533` |

主权重文件为 18,556,688,736 字节；文件大小不等于运行显存要求。本作品直接使用现成预训练模型，没有自行预训练或微调。

## 5. 演示与实验口径

文稿、图和讲稿统一引用 **`20260929t095000z-holdout8`**，冻结源码为 `b4cb91ef67ae2d14d6cc37f9e18cf6c23e36e8ea`。这是 4 个问题、4 个正常的自建合成模板，不是外部独立盲测。全部逐例材料位于：

[`experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/`](../../experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/)

| 演示 | 所选历史过程 |
|---|---|
| h01 | 凭据经辅助函数参数进入日志，展示有限结构下模型候选的修复增量 |
| h03 | 第一候选仍泄露，真实失败反馈进入下一请求，第二候选通过；模型的根因解释仍有错误 |
| h07 | 认证用途合法、输出已脱敏，保持原代码 |

A/B/C 问题例合格修复分别为 3/4、1/4、4/4，完整任务为 7/8、4/8、6/8。A 是本项目固定启发式，不代表成熟扫描器。零实际不必要修改不表示模型零误报：共享门禁可能拒绝错误提案。后续 h05/h06 协议复测、原六例、现场演示及本轮交付检查均单列，不能拼入该批成绩。

## 6. 导出与复检材料

页面可导出所选记录的材料。CLI 也可从上述真实历史新导出，输出目录必须不存在：

```powershell
python -m agent_pilot.bundle export --run experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/h03/C-agent --output runs/candidate-material-01
```

进入这份新材料自己的目录，使用其内置复检程序；输出必须是新文件：

```powershell
Push-Location runs/candidate-material-01
python -B -S -m agent_pilot.bundle recheck --bundle . --output ../candidate-material-01-recheck.json
Pop-Location
```

退出 `0/1/2` 分别是当前独立复检 PASS/FAIL/UNKNOWN，参数或输入错误为 `3`。它不运行模型，但仍必须通过可信隔离门禁。用旧包复检时应运行旧包自带程序；新 verifier 与旧包的代码摘要不一致会阻断，不能通过放松身份检查强行兼容。

三个独立字段必须一起阅读：

- `prior_report_applicable`：旧报告是否仍绑定当前对象和规则。
- `historical_evidence_integrity`：manifest 列明的 `original.py`、`report.json`、`trace/**` 是否完整且未变；状态为 INTACT、DEGRADED 或 UNKNOWN，并列出缺失、变化和不可读文件。它不证明未声明的历史事件齐全，也不是数字签名。
- `validation`：重读当前候选后，固定裁判的真实复检结论。

本轮定向回归的 19 项单测使用明确标注的虚构转录；另做了两次真正隔离复检，各 13 项 PASS。第二次只在新副本删除一项可选轨迹，得到 DEGRADED、旧报告仍适用、当前复检仍 PASS。这说明材料缺失会被报告，并未把历史可审查性和候选行为混为一个结论。[全部命令与退出码](checks/bundle-integrity/20260929T135515Z/command-log.json)可复核；[此前启动记录失败](checks/bundle-integrity/20260929T135237Z/command-log.json)也保留，该次未开始候选执行。

## 7. 候选打包与待确认事项

源码候选包复用 [build-review.py](../../scripts/build-review.py)：从最终固定提交构建，显式指定 `--commit`、版本/标签、来源提交及新输出目录。它只读取指定 Git 提交的跟踪文件，不把变化工作区伪装成该提交；生成 ZIP、manifest 和外部 SHA256 清单。`--tag` 仅记录标签文本，不创建或发布标签。

解压后，在安装依赖、启动服务或生成 `runs` 之前，用包内 [verify-review.py](../../scripts/verify-review.py) 核对文件清单；校验器会拒绝缺失、改动和清单外文件。权重、本机运行设施、虚拟环境及真实凭据不在源码包内。旧评审的 `run-review-checks.py` 对应旧 Gitleaks 流程，不是本候选的新启动命令。

队伍仍需确认匿名处理、实际成员贡献、学校审核、原创声明、AI 使用许可、正式提交要求和文件命名。ChatGPT/Codex 对方案、主要代码、调试、实验组织和文稿的实质参与已经披露；公开模型和框架另列 [来源与归属](../local-agent/reliability/source-attribution.md)。本入口不代签声明、不提交材料、不把“未发现禁止”当成许可。

原始验收器、Agent 首轮和协议修订继续保留为 [历史入口](../../README.md#历史阶段入口)。其中写明的当时状态和路径不自动成为本候选的当前运行说明。

精简候选包包含当前启动与复检依赖、同批八例完整记录及本轮关键证据；历史阶段入口所引用的旧平台与旧整轮深层材料由完整研发包提供，精简包不重复收录。
