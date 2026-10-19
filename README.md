# 密证 CredProof —— 源码与运行说明

**参赛队伍：DUIDUI队**　|　作品：AI 生成安全补丁的可信验收与人机协同修复平台

本目录是作品的**完整源码与可执行程序**。一句话介绍：CredProof 把 Python 工具的修改（不论来自 AI、外包还是开发者自己）放进一次性隔离副本中真实运行，同时检查**不泄密、不乱读、不乱连**三类风险和必要业务是否仍然成立，给出“通过 / 不通过 / 证据不足”三值结论，再由人决定是否采纳，结论可导出、可在新目录复检。图文版介绍见同目录的《项目简介.pdf》。

---

## 一、三分钟上手（推荐评委先做这一步）

**Windows 10 / 11（无需安装任何软件）**

1. 完整解压压缩包（不要只拷贝启动文件）。
2. 双击 `start-credproof.cmd`。程序使用随包的 Python 3.12.10（`runtime/python/`），自动打开浏览器；若 8765 端口被占用会自动换一个空闲端口。
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
| pytest、requests | 见 `credproof_safety/requirements-lock.txt` | 在隔离环境中运行被测项目的业务测试 | 由运行时准备脚本按哈希安装 |
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
     cd /mnt/<解压目录所在盘>/<解压目录>
     python3 scripts/runtime/setup-linux.py --runtime-root ~/credproof-agent-runtime
     ```
  3. 在 Windows 解压目录下新建 `config/local-runtime.json`（可复制 `config/runtime.example.json`）：
     ```json
     { "wsl_distribution": "Ubuntu-24.04", "wsl_user": "", "runtime_root": "~/credproof-agent-runtime" }
     ```
  4. 运行 `check-runtime.cmd` 只读自检；就绪后双击 `start-recheck.cmd`。页面右上角显示“可以检查：隔离环境就绪”。
- **现场模式**：在完成隔离验收准备的基础上，按第四节安装模型，再运行 `scripts\setup-local-agent.cmd`（创建 `.venv` 并安装锁定的 Qwen-Agent 依赖），最后双击 `start-live.cmd`。

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

`doctor` 就绪后，把最后的 `doctor` 换成 `check --config /workspace/<项目>/credproof.toml` 即可。容器的安全配置说明见 `deploy/docker/README.md`；在启用 AppArmor 用户命名空间限制的主机上，还需按该文档加载 `deploy/apparmor/credproof-bwrap`。不加这些参数时，检查器会拒绝降级运行，返回“证据不足”（退出码 3），不会给出“通过”。

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

**模型在系统中的位置**：模型只负责“提出候选修改”，**不参与判定**。候选保存为新版本后状态是“证据不足、待定、未应用”，必须经过同一个隔离检查器和人工决定。模型进程运行在独立的 bubblewrap 边界中：只有回环网络，代码与模型目录只读挂载，看不到项目仓库、修复历史和真实凭据。

**硬件建议**：NVIDIA 显卡，显存 ≥ 24 GB（团队测试机为 32 GB 显存）；无显卡时可用 CPU 运行但非常慢。查看、修订、审批、检查与复检**都不需要显卡**。

### 4.2 安装与配置（在 WSL 或 Linux 中，接第三节的运行时目录）

```sh
RT=~/credproof-agent-runtime                      # 与 local-runtime.json 中的 runtime_root 一致
# 1) Agent 依赖装进运行时 venv（模型边界只读挂载这个目录）
$RT/venv/bin/pip install -r agent_pilot/requirements-lock.txt
# 2) Ollama：从官方发布页下载 Linux amd64 版本，解压到 $RT/ollama（应得到 $RT/ollama/bin/ollama）
# 3) 把模型下载到运行时的模型目录
OLLAMA_MODELS=$RT/models $RT/ollama/bin/ollama serve &          # 临时启动一次，用于下载
OLLAMA_MODELS=$RT/models $RT/ollama/bin/ollama pull qwen3-coder:30b
OLLAMA_MODELS=$RT/models $RT/ollama/bin/ollama pull qwen2.5-coder:32b-instruct-q4_K_M   # 可选
kill %1                                                          # 下载完成后停止；现场模式会在隔离边界内自行启动
```

- 选择模型：设置环境变量 `CREDPROOF_MODEL_PROFILE=qwen3`（默认）或 `qwen25`。
- 程序会核对模型清单摘要，不做任何自动回退：`qwen3` 为 `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`，`qwen25` 为 `b92d6a0bd47ee79114298de0177bf920c05a706d12633950b3936778492bef41`。若上游更新了同名标签导致摘要不同，现场模式会拒绝启动并说明原因。
- Windows 主机侧：运行 `scripts\setup-local-agent.cmd`（Python 3.12 虚拟环境 + 锁定依赖），然后 `start-live.cmd`；`check-runtime.cmd` 会只读检查隔离材料与模型清单是否就绪。
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
docs/                    工作台展示用的冻结数据（评测结果、对照表、CI 结果、外部组件记录、审阅快照）与接口约定 PRODUCT-API.md
experiments/             历史 Agent 试点案例 h01/h03/h07 的原始记录（首页“案例回放”使用）
runtime/python/          Windows 随包 Python 3.12.10（官方嵌入式发行版，保留其许可）
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
   团队在 Linux 上对本发布目录的结果：311 项通过，16 项因需要 Windows/WSL 或 Git 历史而跳过，0 失败。
2. **真实隔离检查**（隔离运行时就绪后）：第五节的两条命令应分别得到退出码 2 和 0。团队在 Ubuntu 24.04 原生 bubblewrap 上用本发布目录实测：b07 不通过（禁止服务收到 1 次带凭据请求）、资料助手修复版通过、资料助手原版不通过。
3. **浏览器端到端**（隔离验收模式）：新建检查 → 资料助手示例 → 检查（不通过）→ 提交修订 → 检查（通过）→ 采纳（功能测试）→ 导出 → 复检导出包（通过）；上传一个不带配置的项目也能完成识别与检查。团队已按此流程在本发布目录上实测通过。

---

## 八、数据与隐私

- 所有凭据都是每次检查随机生成的合成值，所有服务都是隔离环境内的本地模拟服务，不涉及任何真实账户或外部系统。
- 报告只记录凭据出现的通道名和次数，从不保存凭据值。
- 上传的项目只保存在本机工作目录 `runs/intake/` 下；系统从不写回原项目。
- 发布包不包含模型权重、隔离运行时、虚拟环境或任何真实凭据。

## 九、常见问题

- **双击后窗口一闪而过 / 提示无法启动**：请确认已完整解压（含 `runtime/python/`），并检查系统 TEMP 目录可写。
- **页面显示“隔离环境未就绪”**：查看模式下这是正常的；需要真实检查时按第三节准备运行时，再用 `start-recheck.cmd` 启动。
- **端口被占用**：启动器会自动换用空闲端口，并在窗口中打印实际地址。
- **现场模式提示模型清单不一致**：说明本机下载的模型与作品固定的版本不同，按第四节核对摘要；程序不会自动换用其他模型。

## 十、第三方组件

见 `THIRD_PARTY_NOTICES.md`。
