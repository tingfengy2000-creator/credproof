# 密证 CredProof —— 源码与运行说明

**参赛队伍：DUIDUI队**　|　作品：AI 生成安全补丁的可信验收与人机协同修复平台

本目录是作品的**完整源码与可执行程序**。界面怎么用，请看同目录的《评委操作手册.pdf》（含启动方法与各页面的操作步骤）。一句话介绍：CredProof 把 Python 工具的修改（不论来自 AI、外包还是开发者自己）放进一次性隔离副本中真实运行，同时检查**不泄密、不乱读、不乱连**三类风险和必要业务是否仍然成立，给出“通过 / 不通过 / 证据不足”三值结论，再由人决定是否采纳，结论可导出、可在新目录复检。图文版介绍见同目录的《项目简介.pdf》。

---

## 一、三分钟上手（推荐评委先做这一步）

**Windows 10 / 11（无需安装任何软件）**

1. 完整解压压缩包（不要只拷贝启动文件）。
2. 双击 `密证CredProof.exe`（与双击 `start-credproof.cmd` 完全等价）。程序使用随包的 Python 3.12.10（`runtime/python/`），自动打开浏览器；若 8765 端口被占用会自动换一个空闲端口。
3. 关闭时在黑色窗口按 `Ctrl+C`。

**macOS / Linux**：需要已安装 Python ≥ 3.11，在本目录运行 `sh start-credproof.sh`。

**推荐浏览路径**（查看模式下全部可用）：

| 顺序 | 页面 | 看什么 |
|---|---|---|
| 1 | 首页 | 一个真实案例：原问题 → AI 候选（不通过）→ 开发者修订（通过）→ 待人工采纳 → 导出复检；可切换三个版本对比“五个问题” |
| 2 | 新建检查 | 选“资料助手”示例，看自动识别入口、测试与凭据变量后生成的配置向导，以及 `credproof.toml` 实时预览 |
| 3 | 我的项目 | 打开审阅记录：三种状态、五个问题、14 项条件、代码差异、版本链、人工决定 |
| 4 | 对照与接入 | 88 条冻结记录上五种方法的对照；开源组件 python-dotenv 的接入记录 |
| 5 | 流水线闸门 | GitHub Actions 上两个拉取请求、原生与加固容器两种作业的真实结果 |

> 查看模式不执行被测代码、不启动模型，所有既有记录均为真实运行留下的历史材料。真实检查和复检请看第三节。

---

## 二、三种运行模式

| 模式 | 启动方式 | 需要的环境 | 能做什么 |
|---|---|---|---|
| **查看** | `start-credproof.cmd` / `start-credproof.sh` | 无（Windows 随包 Python） | 浏览全部真实记录；接入项目、填写配置、修订代码、记录决定（只作用于临时副本）；检查与复检由后端拒绝 |
| **隔离验收** | `start-recheck.cmd`，或 `python -m agent_pilot.launch --demo --mode recheck` | Linux 隔离运行时（Windows 上为 WSL2） | 以上全部 + 真实隔离检查、导出包复检、命令行与 CI 门禁；**不调用模型** |
| **现场** | `start-live.cmd`，或 `--mode live` | 隔离运行时 + 本地 Ollama 与 Qwen 模型 | 以上全部 + “请本地模型提出候选”（候选只生成新版本，仍需检查与人工决定） |

所有模式都只监听 `127.0.0.1`，不上传代码，不调用任何付费 API。

---

## 三、按系统准备环境

### 3.1 依赖总览

| 组件 | 版本 | 用途 | 何时需要 |
|---|---|---|---|
| Python | 3.12（≥3.11 可运行查看模式） | 程序本体；核心包**只用标准库** | 始终 |
| bubblewrap | Ubuntu 24.04 官方包 | 无特权命名空间隔离 | 隔离验收、现场 |
| 隔离运行时 | `scripts/runtime/setup-linux.py` 生成 | 只读 rootfs、固定 bwrap、受控 venv（pytest 等） | 隔离验收、现场 |
| pytest 及其依赖 | 见 `credproof_safety/requirements-lock.txt` | 在隔离环境中运行被测项目的业务测试 | 由运行时准备脚本按哈希安装；额外项目依赖需另行适配 |
| Qwen-Agent、ollama（Python） | 0.0.34、0.6.0，完整锁定见 `agent_pilot/requirements-lock.txt` | 本地模型候选与 Agent 试点 | 现场模式、全部测试 |
| Ollama + Qwen 模型 | 见第四节 | 本地推理 | 现场模式 |
| Docker | 24 及以上 | 加固容器中运行检查 | 可选（CI） |

### 3.2 Windows 10 / 11

- **查看模式**：无需准备，双击 `start-credproof.cmd`。
- **隔离验收**（检查在 WSL2 内执行，Windows 只运行工作台）：
  1. 安装 WSL2 与 Ubuntu 24.04：`wsl --install -d Ubuntu-24.04`。
  2. 在 Ubuntu 中安装系统包并准备运行时（系统 `python3` 必须是 Ubuntu 24.04 自带的 3.12）：
     ```sh
     sudo apt-get install -y python3 python3-venv bubblewrap ca-certificates libseccomp2
     cd "/mnt/<解压目录所在盘>/<解压目录>"
     python3 scripts/runtime/setup-linux.py --runtime-root ~/credproof-agent-runtime
     CREDPROOF_RUNTIME_ROOT=~/credproof-agent-runtime python3 -m credproof_safety doctor
     ```
  3. 在 Windows 解压目录下新建 `config/local-runtime.json`（可复制 `config/runtime.example.json`）：
     ```json
     { "wsl_distribution": "Ubuntu-24.04", "wsl_user": "", "runtime_root": "~/credproof-agent-runtime" }
     ```
  4. 上一步 `doctor` 返回 `ready=true`、退出码 0，表示纯检查运行时就绪。Windows 侧可用随包 Python 只读核对工作台能否找到它：
     ```bat
     runtime\python\python.exe -S -c "from credproof_safety.runner import available; print(available())"
     ```
  5. 先关闭查看模式的服务窗口，再启动隔离验收。已有可用 Windows Python 的电脑可双击 `start-recheck.cmd`；未安装 Python 时，在解压目录的命令提示符中使用随包解释器：
     ```bat
     runtime\python\python.exe -S -m agent_pilot.launch --demo --mode recheck --auto-port --open-browser
     ```
     页面右上角应显示“可以检查：隔离环境就绪”。`start-recheck.cmd` 本身调用 PATH 中的 `python`，不自动选择随包解释器，也不自动换端口；命令行方式可避免这两项准备差异。
- **现场模式**：按第四节准备独立模型运行时，并安装完整 Windows Python 3.12，再运行 `scripts\setup-local-agent.cmd` 创建主机侧 `.venv`，最后启动 `start-live.cmd`。随包嵌入式 Python 用于零安装查看和固定检查，不用于创建这个开发虚拟环境。

`check-runtime.cmd` 检查的是**模型运行时**的完整探针与模型文件，不是纯检查运行时的 `doctor`。第三节尚未安装模型时，该命令报告模型未就绪是正常的，不影响页面按 `runner.available()` 执行固定检查。已有目录若缺少匹配的准备收据，请保留旧目录并选择新的 `--runtime-root`，不要覆盖或手改清单。包含中文或空格的解压路径，在 WSL 的 `cd` 命令中须用引号包住完整路径。

### 3.3 Linux（Ubuntu 24.04 x86_64，原生运行）

```sh
sudo apt-get install -y python3 python3-venv bubblewrap ca-certificates libseccomp2
python3 scripts/runtime/setup-linux.py --runtime-root ~/credproof-runtime     # 以普通用户运行，不要用 root
cat > ~/credproof-runtime.json <<'EOF'
{"runtime_root": "~/credproof-runtime"}
EOF
export CREDPROOF_CONFIG=~/credproof-runtime.json
python3 -m credproof_safety doctor                                           # 0 = 隔离就绪，4 = 未就绪并给出提示
python3 -m agent_pilot.launch --demo --mode recheck --auto-port --open-browser
```

准备脚本会下载固定版本的 bubblewrap 官方包和带哈希的 PyPI wheel，逐字节校验后生成只读 rootfs；已有运行时不会被覆盖，失败时请换一个新目录重试。Ubuntu 22.04、Debian 12 不在支持范围内。

### 3.4 macOS

仅支持查看模式：`sh start-credproof.sh`（需 Python ≥ 3.11）。隔离检查依赖 Linux 命名空间，可在 Linux 虚拟机或下面的 Docker 方式中运行。

### 3.5 Docker 与 CI 流水线

```sh
docker build --platform linux/amd64 -f deploy/docker/Dockerfile --build-arg SOURCE_COMMIT=release -t credproof:release .
mkdir -p credproof-out
docker run --rm --network none --read-only --tmpfs /tmp:exec \
  --cap-drop ALL --security-opt no-new-privileges \
  --security-opt seccomp=deploy/docker/seccomp-credproof.json --security-opt systempaths=unconfined \
  -v "$PWD:/workspace:ro" -v "$PWD/credproof-out:/out" credproof:release doctor
```

`doctor` 就绪后，把最后的 `doctor` 换成 `check --config /workspace/<项目>/credproof.toml` 即可。容器以非 root、只读根文件系统、无网络、去除全部能力并使用固定 seccomp 配置运行；在启用 AppArmor 用户命名空间限制的主机上，还需为 bubblewrap 加载 `deploy/apparmor/credproof-bwrap`。不加这些参数时，检查器会拒绝降级运行，返回“证据不足”（退出码 3），不会给出“通过”。

GitHub Actions 示例：`.github/workflows/credproof.yml` 定义了 Runner 原生与加固容器两个作业，输出 SARIF、JUnit 与中文摘要；`examples/ci/credproof-safety.yml.example` 是自托管 Runner 的最小示例。

---

## 四、大模型与 Agent：选型、安装与配置

### 4.1 选型

| 项 | 选择 | 说明 |
|---|---|---|
| 推理服务 | **Ollama**（本地运行，启用 `OLLAMA_NO_CLOUD=1`） | 不调用任何付费或云端 API |
| 默认模型 | **Qwen3-Coder 30B**（`qwen3-coder:30b`，Q4_K_M 量化，配置名 `qwen3`） | 页面“请本地模型提出候选”默认使用 |
| 备选模型 | **Qwen2.5-Coder 32B Instruct**（`qwen2.5-coder:32b-instruct-q4_K_M`，配置名 `qwen25`） | 对照评测与历史案例使用 |
| Agent 框架 | **Qwen-Agent 0.0.34**（原生结构化工具调用） | 命令行 `repair --strategy qwen_agent`：读取允许的代码与脱敏证据、提交候选、接收程序验收反馈 |
| 受限补丁策略 | `bounded_patch`（单次结构化请求，返回 PATCH/STOP） | 网页“请本地模型提出候选”与 `repair --strategy bounded_patch` 使用 |

**模型在系统中的位置**：模型只负责“提出候选修改”，**不参与判定**。候选保存为新版本后状态是“证据不足、待定、未应用”，必须经过同一个隔离检查器和人工决定。模型进程运行在独立的 bubblewrap 边界中：只有回环网络，仅挂载本次程序准备的授权代码工作包、依赖、所选模型文件和必要驱动；不挂载整个项目仓库、修复历史或真实凭据。生成请求仍会包含授权入口、必要测试和脱敏反馈。

**硬件与支持环境**：本版现场入口的已验证环境是 **Windows + WSL2 Ubuntu 24.04 + NVIDIA CUDA**，测试环境有 32 GB 显存。现有启动器明确挂载 WSL 驱动与 `/dev/dxg`，并选择 CUDA 后端；不能把原生 Linux 或纯 CPU 的 Ollama 可运行等同于本入口已验证。查看、人工修订、审批、固定检查与复检**都不需要显卡**。

### 4.2 需要另行下载的内容（体积较大，不随包分发）

查看模式和隔离验收都**不需要**下载下列模型；只有现场模式（请本地模型提出候选）才需要。

| 内容 | 大小 | 官方下载 / 安装说明 |
|---|---|---|
| Ollama（Linux amd64 完整归档） | 较大（含 CUDA 运行库） | 发布页：<https://github.com/ollama/ollama/releases>；Linux 手动安装说明：<https://docs.ollama.com/linux>（归档地址 `https://ollama.com/download/ollama-linux-amd64.tar.zst`） |
| Qwen3-Coder 30B（`qwen3-coder:30b`，默认） | 约 19 GB | <https://ollama.com/library/qwen3-coder> |
| Qwen2.5-Coder 32B Instruct（`qwen2.5-coder:32b-instruct-q4_K_M`，可选） | 约 20 GB | <https://ollama.com/library/qwen2.5-coder> |
| Qwen-Agent 0.0.34 | 随 `pip install -r agent_pilot/requirements-lock.txt` 自动安装 | 项目主页：<https://github.com/QwenLM/Qwen-Agent> |
| WSL2 + Ubuntu 24.04（Windows 上做隔离检查时需要） | — | <https://learn.microsoft.com/windows/wsl/install>（命令 `wsl --install -d Ubuntu-24.04`） |
| Python 3.12（Windows 开发环境或现场模式主机侧需要） | — | <https://www.python.org/downloads/windows/> |

模型通过 `ollama pull` 下载（见 4.3），程序会核对模型清单摘要；如果上游已更新同名标签，现场模式会拒绝启动并说明原因，不会自动换用其他模型。

### 4.3 安装与配置（当前现场入口：Windows + WSL2）

**与第三节的纯检查运行时分开准备。** `setup-linux.py` 会固定其 venv 文件清单；之后直接往同一目录安装 Agent 依赖，会使原准备收据失效。为模型另选新的版本化目录，在依赖安装完成后使用现有 `agent_pilot.isolation` 入口准备和探测模型运行边界；不要修改已有 rootfs、清单或探针结果来标记就绪。以下准备命令在解压目录对应的 WSL 路径中、以普通用户运行：

```sh
RT="$HOME/credproof-model-runtime"                  # 选择尚不存在的新目录
python3 -m venv "$RT/venv"
"$RT/venv/bin/python" -m pip install --require-hashes -r credproof_safety/requirements-lock.txt
"$RT/venv/bin/python" -m pip install -r agent_pilot/requirements-lock.txt
CREDPROOF_RUNTIME_ROOT="$RT" python3 -m agent_pilot.isolation prepare
CREDPROOF_RUNTIME_ROOT="$RT" python3 -m agent_pilot.isolation probe
```

最后一条须返回 `ready=true`。它只执行固定的无害边界探针，不调用模型。缺依赖、权限或探针失败时先停止，不使用旧探针代替。

从 [Ollama 官方发布页](https://github.com/ollama/ollama/releases) 获取 Linux amd64 **完整归档**（现有运行记录使用 0.34.4），按发布页的校验信息核对后解压到 `$RT/ollama`：须同时有 `bin/ollama` 和 `lib/ollama/`，包括启动器使用的 `cuda_v12` 库，不能只复制可执行文件。手动归档的安装说明见 [官方 Linux 文档](https://docs.ollama.com/linux)。以下为模型环境准备步骤；查看和固定检查不需要下载模型权重。

下载模型是联网准备阶段；推理阶段由程序另启隔离服务。先确认下面的准备端口未被占用，避免把模型下载进另一份已运行服务的目录：

```sh
export OLLAMA_HOST=127.0.0.1:11436
export OLLAMA_MODELS="$RT/models"
export OLLAMA_NO_CLOUD=1
"$RT/ollama/bin/ollama" serve > "$RT/model-download.log" 2>&1 &
OLLAMA_PREP_PID=$!
# 确认本进程仍在运行，并在另一终端确认此地址的服务已就绪后执行 pull。
"$RT/ollama/bin/ollama" pull qwen3-coder:30b
# 仅需要备选模型时再下载；不是启动查看/检查模式的必要条件。
# "$RT/ollama/bin/ollama" pull qwen2.5-coder:32b-instruct-q4_K_M
kill "$OLLAMA_PREP_PID"                            # 只停止本次启动的准备进程
wait "$OLLAMA_PREP_PID" 2>/dev/null || true
unset OLLAMA_HOST OLLAMA_MODELS OLLAMA_NO_CLOUD
```

在 Windows 的 `config/local-runtime.json` 中把 `runtime_root` 改为这份模型运行时（例如 `~/credproof-model-runtime`）；WSL 发行版和用户保持实际值。需要回到第三节独立的纯检查运行时，切回其目录即可。配置及模型目录只放在操作者机器上，不打进发布包。

- 选择模型：设置环境变量 `CREDPROOF_MODEL_PROFILE=qwen3`（默认）或 `qwen25`。
- 程序会核对模型清单摘要，不做任何自动回退：`qwen3` 为 `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`，`qwen25` 为 `b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41`。若上游更新了同名标签导致摘要不同，现场模式会拒绝启动并说明原因。
- Windows 主机侧：安装完整 Python 3.12 后，运行 `scripts\setup-local-agent.cmd`（创建 Python 3.12 虚拟环境并安装锁定依赖），再运行 `check-runtime.cmd`，确认保存的完整隔离探针、模型清单及文件就绪后启动 `start-live.cmd`。此自检只读，不等于执行了新的模型边界实验；实际提案仍须通过本次启动的边界检查。旧案例工作台的现场任务另需可信安装解释器 `program_python`，未配置会明确拒绝，不回退到历史安装。
- 预算上限（防止无限调用）：单任务最多 4 次模型请求、3 个候选、上下文 16K、单次请求 120 秒、总计 900 秒；网页单次提案只发 1 次请求。

---

## 五、命令行用法

```sh
python -m credproof_safety init --project <项目目录> [--write]        # 预览/生成 credproof.toml，默认不覆盖
python -m credproof_safety doctor                                     # 用固定无害载荷自检隔离环境
python -m credproof_safety check --config <项目>/credproof.toml \
       --sarif out.sarif --junit junit.xml --summary summary.md        # 隔离检查
python -m credproof_safety export-tests --config <项目>/credproof.toml --output tests/credproof-regression
python -m credproof_safety repair --config <项目>/credproof.toml --strategy bounded_patch   # 需现场模式环境
```

| 退出码 | 含义 | 流水线动作 |
|---|---|---|
| 0 | PASS：14 项必要条件全部满足 | 放行，进入人工审阅 |
| 2 | FAIL：存在明确反例（泄密、越界读取、未授权访问或业务未保持） | 拦下 |
| 3 | UNKNOWN：证据不足（如隔离未建立、必要测试未执行） | 拦下，排除环境原因后重查 |
| 4 | 配置、参数或环境错误 | 拦下，修正后重试 |

快速体验（隔离运行时就绪后）：

```sh
python -m credproof_safety check --config examples/bench/b07-webhook-relay/project/credproof.toml   # 跟随跳转泄露凭据 → 退出码 2
python -m credproof_safety check --config examples/material_assistant_fixed/credproof.toml          # 修复版 → 退出码 0
```

---

## 六、源码结构

```
credproof_safety/        核心：配置解析、隔离运行器、14 项条件判定、人工审阅与版本绑定、导出复检、SARIF/JUnit、命令行
  config.py  runner.py  project.py  human_review.py  project_bundle.py  report_formats.py  cli.py
  agent.py  proposal.py  runtime_setup.py  doctor.py ...   模型边界与候选生成、Linux 运行时准备与自检
  tests/                 核心测试
credproof_access/        受控访问组件：read_text(path) 只读授权目录；get_json(url, credential) 只访问授权服务且不跟随跳转
agent_pilot/             本机工作台
  web.py launch.py       标准库 HTTP 服务（只监听 127.0.0.1，会话令牌，Host/Origin 校验，严格 CSP）与启动器
  intake.py              上传接入：大小/数量限制、条目校验、AST 静态识别入口与测试、配置向导
  evidence_view.py       把 14 项条件归纳为“五个问题”（只读派生，不产生新结论）
  presentation.py        历史案例与审阅快照的只读加载（逐文件摘要校验）
  model_client.py tools.py bounded_patch.py ...   Qwen-Agent 客户端、工具定义与受限补丁策略
  ui/                    单页前端（index.html、styles.css、app.js，无外部依赖）
  tests/                 工作台、接口、上传、审阅流程等测试
credproof/               早期验收器原型（Gitleaks 扫描 + 单行修复契约），保留用于对照
examples/                资料助手（问题版/修复版）、8 个评测目标 b01–b08（含参考修复）、python-dotenv 适配示例、CI 示例
scripts/                 bench（评测生成/裁判/汇总）、compare（对照表生成）、ci（流水线作业）、runtime（运行时准备与镜像扫描）、delivery（启动与打包工具）及演示脚本
deploy/                  Dockerfile、seccomp 与 AppArmor 配置
docs/                    工作台展示用的冻结数据（评测结果、对照表、CI 结果、外部组件记录、审阅快照）
experiments/             历史 Agent 试点案例 h01/h03/h07 的原始记录（首页“案例回放”使用）
runtime/python/          Windows 随包 Python 3.12.10（官方嵌入式发行版，保留其许可）
密证CredProof.exe        Windows 双击启动器（运行 start-credproof.cmd；源码在 scripts/delivery/launcher/）
start-*.cmd / .sh        启动脚本；check-runtime.cmd 为只读环境自检
```

---

## 七、自检：确认作品完整可运行

1. **全部单元与协议测试**（任何系统，Python 3.12）：
   ```sh
   python -m venv .venv && . .venv/bin/activate          # Windows：py -3.12 -m venv .venv && .venv\Scripts\activate
   pip install -r agent_pilot/requirements-lock.txt
   pip install -e ".[test]"
   python -m pytest agent_pilot/tests credproof_safety/tests tests
   ```
   团队在 Linux 上对本发布目录的结果：311 项通过，17 项因需要 Windows/WSL、Git 历史或原始 CI 记录而跳过，0 失败。
2. **真实隔离检查**（隔离运行时就绪后）：第五节的两条命令应分别得到退出码 2 和 0。团队在 Ubuntu 24.04 原生 bubblewrap 上用本发布目录实测：b07 不通过（禁止服务收到 1 次带凭据请求）、资料助手修复版通过、资料助手原版不通过。
3. **浏览器端到端**（隔离验收模式）：新建检查 → 资料助手示例 → 检查（不通过）→ 提交修订 → 检查（通过）→ 采纳（功能测试）→ 导出 → 复检导出包（通过）；上传一个不带配置的项目也能完成识别与检查。团队已按此流程在本发布目录上实测通过。

---

## 八、数据与隐私

- 所有凭据都是每次检查随机生成的合成值，所有服务都是隔离环境内的本地模拟服务，不涉及任何真实账户或外部系统。
- 报告只记录凭据出现的通道名和次数，从不保存凭据值。
- 上传的项目只保存在本机工作目录 `runs/intake/` 下；系统从不写回原项目。
- 发布包不包含模型权重、隔离运行时、虚拟环境或任何真实凭据。

## 九、常见问题

- **双击 `密证CredProof.exe` 时出现“Windows 已保护你的电脑”**：这是系统对未签名程序的常规提示，点“更多信息”→“仍要运行”即可；也可以直接双击 `start-credproof.cmd`，效果相同。该启动器只是在同一窗口中运行 `start-credproof.cmd`，源码见 `scripts/delivery/launcher/launcher.c`，可用其中的 `build.sh` 重新编译。
- **双击后窗口一闪而过 / 提示无法启动**：请确认已完整解压（含 `runtime/python/`），并检查系统 TEMP 目录可写。
- **页面显示“隔离环境未就绪”**：查看模式下这是正常的；需要真实检查时按第三节准备运行时，再用 `start-recheck.cmd` 启动。
- **端口被占用**：启动器会自动换用空闲端口，并在窗口中打印实际地址。
- **现场模式提示模型清单不一致**：说明本机下载的模型与作品固定的版本不同，按第四节核对摘要；程序不会自动换用其他模型。

## 十、第三方组件

见 `THIRD_PARTY_NOTICES.md`。
