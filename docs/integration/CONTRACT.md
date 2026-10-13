# 第三、四步契约：Linux / Docker 运行时与 CI 接入

状态：`DRAFT_FOR_TINGFENG`（5060 起草，2026-10-13）。tingfeng 确认后冻结；实现中如需改动本契约，先改文档、再改代码。
适用主线：`feat/frontend-human-review-5060` @ `37b03f7`。

## 0. 目标与非目标

本轮把 CredProof 从“Windows + WSL 上的工作台”变成两种可以直接卖给企业的形态：

1. **容器 / Linux 部署**：任何 Linux 主机或容器平台用同一个镜像运行检查，不依赖 Windows、WSL 或 GPU。
2. **CI 闸门**：在拉取请求（PR）上自动检查，不安全就让流水线变红，并在 GitHub 的代码扫描页面、JUnit 报告和流水线摘要里给出具体违规事实。

非目标：不改 14 项条件和判定规则；不改 bench-v1 冻结契约；不在 CI 中调用模型；不发布公开镜像仓库（会暴露账号，见第 8 节）；不支持 Windows 原生 CI runner。

## 1. 5060 预研实测（Linux 容器，2026-10-13）

在 Docker 29.8.2 上用 Ubuntu 24.04（noble）最小系统、`bubblewrap 0.9.0`、`python3 3.12.3` 搭了原型镜像。程序是主线 `37b03f7` 的源码，检查器和命令行均未改动：

| 运行参数 | 结果 |
| --- | --- |
| Docker 默认参数（默认 seccomp、默认 /proc 屏蔽） | bwrap 无法创建命名空间；检查器**安全失败**，返回 `UNKNOWN / sandbox_execution_incomplete`，不会误报 PASS |
| 只加 `seccomp=unconfined` | 挂载 /proc 失败（Docker 的 /proc 屏蔽路径阻止新 proc 挂载） |
| 只加 `--cap-add SYS_ADMIN` | `pivot_root` 被拒 |
| `seccomp=unconfined` + `systempaths=unconfined`，**非 root 用户，不加任何能力** | 可用 |
| 上一行再加 `--network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges` | 可用 |
| 在上一行环境中运行 `check_variant.py`：b07 漏洞原版 | `FAIL`：required_entry_scenarios、no_forbidden_service_receipt、no_unauthorized_connection（与主机结果一致） |
| 同上：b07 参考修复 | `PASS` |
| 同上：`python -m credproof_safety check --config …` | 命令行正常，FAIL 时退出码 2 |

结论：容器内运行可行，**不需要 `--privileged`，也不需要额外能力**。必须放开的两项限制是 seccomp 中的命名空间和挂载相关调用，以及 /proc 屏蔽。容器本身可以完全断网，因为模拟服务位于沙箱内部的回环网络。

尚未实测：带 AppArmor 的宿主（Ubuntu 23.10 以后默认限制非特权用户命名空间，GitHub 的 ubuntu-24.04 runner 属于此类）、自定义 seccomp profile，以及 GitHub Actions 实际运行。这些都列入验收（第 6 节）。

## 2. 第四步：统一 Linux 运行时

### 2.1 一个安装脚本，三处共用

新增 `scripts/runtime/setup-linux.py`。WSL、原生 Linux 和 Docker 构建**都只用这一个脚本**准备运行时，避免三套布局各自漂移。

- 以非 root 用户运行，目标目录由 `--runtime-root` 指定，默认 `~/credproof-agent-runtime`。布局保持 `agent_pilot.runtime_config.runtime_paths()` 的现有约定，不改。
- **专用沙箱根文件系统**：复用 `agent_pilot.sandbox_runner.prepare()` 的做法，从系统 Python 复制解释器、标准库和依赖库到 `isolation/rootfs`；bwrap 使用已固定摘要的 Ubuntu 包。
  - **禁止把 `/` 软链接成 rootfs**。5060 的 Linux 临时环境用过这种做法，会让被检查代码以只读方式看到宿主（或容器）的全部文件，包括被检查仓库的其他文件和程序本身。
- **运行时依赖**：用 `credproof_safety/requirements-lock.txt` 创建 `venv`，并以 `pip install --require-hashes` 安装。锁文件目前没有哈希，需要补齐；补哈希属于锁定依赖变更，由 5090 负责。
- 写出 `runtime.json`（只含 `runtime_root`），最后自动运行 `doctor`（2.4 节）并打印结果。
- 幂等：重复运行时不破坏已有运行时；材料摘要变化时要求先删除旧运行时再重建，不静默覆盖。

### 2.2 Docker 镜像

新增 `deploy/docker/Dockerfile`，用多阶段构建：

1. `base`：`ubuntu:24.04`，**固定镜像摘要（digest）**。`apt` 安装 `python3 python3-venv bubblewrap ca-certificates libseccomp2`，并把实际版本记录进构建收据。
2. `runtime`：以非 root 用户运行 `setup-linux.py --runtime-root /opt/credproof-runtime`。
3. `final`：在 `base` 上复制 `/opt/credproof-runtime`，并安装**同一提交构建的 wheel**（`credproof_safety-<版本>-py3-none-any.whl`），装到独立的 `/opt/credproof/venv`。
   - 创建用户 `checker`（uid 10001）。
   - 设置 `ENV CREDPROOF_CONFIG=/opt/credproof-runtime/runtime.json`。
   - `WORKDIR /workspace`。
   - `ENTRYPOINT ["/opt/credproof/venv/bin/credproof-safety"]`。

镜像内不得包含：模型及 Ollama、qwen-agent、`.git`、`docs/handoff/**`、`docs/review/**`、`experiments/**`、真实凭据、作者路径。用第 7 节的扫描检查镜像文件系统，敏感命中必须为 0。

镜像标签用 `credproof:<pyproject 版本>`，并在构建收据中记录源码提交、wheel 摘要、基础镜像摘要和 apt 包版本。**不推送到任何公开镜像仓库。**

### 2.3 运行参数（写进文档和示例，不得放宽）

```text
docker run --rm \
  --network none --read-only --tmpfs /tmp:exec \
  --cap-drop ALL --security-opt no-new-privileges \
  --security-opt seccomp=deploy/docker/seccomp-credproof.json \
  --security-opt systempaths=unconfined \
  [--security-opt apparmor=<见下>] \
  -v "$PWD:/workspace:ro" -v "$PWD/credproof-out:/out" \
  credproof:<版本> check --config /workspace/<路径>/credproof.toml \
    --output /out/report.json --sarif /out/credproof.sarif \
    --junit /out/credproof-junit.xml --summary /out/summary.md
```

- **禁止** `--privileged`、`--cap-add`、以 root 运行，以及 `--network host`。
- `deploy/docker/seccomp-credproof.json`：以 moby 某个**固定版本**的默认 profile 为基础，仅额外放行 bwrap 必需的调用：`unshare`、带命名空间标志的 `clone`/`clone3`、`mount`、`umount2`、`pivot_root`、`setns`。文件头部注明来源版本和改动清单。`seccomp=unconfined` 只作为排障手段写进文档，不作为默认值。
- AppArmor：在限制非特权用户命名空间的宿主上（`/proc/sys/kernel/apparmor_restrict_unprivileged_userns` 为 1），只能二选一：要么提供允许 `userns` 的 AppArmor profile（推荐，文件 `deploy/apparmor/credproof-bwrap`），要么 `apparmor=unconfined`。由实测决定采用哪种并写进文档，**不得静默修改宿主的 sysctl**。
- `/workspace` 只读挂载。检查器只在临时目录中复制和运行，输出只写到 `/out`。

### 2.4 `doctor` 自检命令

新增 `credproof-safety doctor`。它不运行任何项目代码，只用固定的自检载荷检查环境，用来区分“环境不可用”和“代码不安全”：

- 检查项：运行时配置可读；rootfs、bwrap、site-packages 存在；bwrap 能创建 user/net/pid/mount 命名空间并挂载 /proc；沙箱内 `python3 -I` 可运行、pytest 可导入；运行时临时目录可写。
- 输出 JSON：`{"ready": bool, "checks": {...}, "hints": [...]}`。hints 是给运维的下一步提示，例如“容器缺少 systempaths=unconfined”或“宿主 AppArmor 限制用户命名空间”。
- 退出码：就绪为 0，否则为 4。
- 以上内容由 `credproof_safety/doctor.py` 实现，`cli.py` 只负责调用。

### 2.5 原生 Linux（不用 Docker）

文档 `docs/integration/linux.md` 说明原生 Linux 的用法：

1. `apt install python3 python3-venv bubblewrap`；
2. `python3 scripts/runtime/setup-linux.py`；
3. `credproof-safety doctor`；
4. `credproof-safety check …`。

支持范围：x86_64、Ubuntu 22.04/24.04、Debian 12。其中只有实测通过的版本才能写成“已验证”。

## 3. 第三步：CI 接入

### 3.1 命令行输出与退出码（保持现有退出码，不改语义）

| 结果 | 退出码 |
| --- | --- |
| PASS | 0 |
| FAIL | 2 |
| UNKNOWN（证据不足，包括环境不可用） | 3 |
| ERROR（配置错误、参数错误、doctor 未就绪） | 4 |

- 修正：`argparse` 参数错误目前也返回 2，会与 FAIL 混淆。改为返回 4。
- `check` 新增可选输出：`--sarif <文件>`、`--junit <文件>`、`--summary <文件>`。
  - 三者都只根据同一份报告 JSON 生成，不重新运行任何东西。
  - 文件中只出现**相对于配置文件所在目录的路径**，不出现绝对路径、主机名或用户名。
- 标准输出仍是原有的报告 JSON，保持兼容。
- CI 闸门规则：**非 0 即失败**。UNKNOWN 也让流水线失败（安全失败），摘要中写明原因，区分“环境没准备好”和“证据不完整”。

### 3.2 SARIF 2.1.0 映射

实现位置：`credproof_safety/report_formats.py`。它是纯函数，输入报告字典，输出 SARIF 字典，不执行代码、不读取项目文件。

- `runs[0].tool.driver`：
  - `name` 为 `CredProof`，`version` 为包版本；**不写 `informationUri`**（匿名期间不放仓库链接）。
  - `rules` 固定为 16 条：14 项条件各一条，再加 `credproof/evidence_incomplete` 和 `credproof/environment_unavailable`。
    - 规则 id 用 `credproof/<条件键>`，例如 `credproof/no_forbidden_service_receipt`。
    - `shortDescription` 用中文条件名，`fullDescription` 说明该条件观察的是什么。
    - `properties.tags` 包括 `security` 和条件所属的组（业务保持 / 不泄密 / 不乱读 / 不乱连 / 隔离）。
    - `defaultConfiguration.level` 为 `error`。
- `results`：
  - **PASS**：空数组。
  - **FAIL**：每个 `required_checks` 为 false 的条件生成一条，`level: error`。
  - **UNKNOWN**：生成一条 `credproof/evidence_incomplete`；若 `doctor` 或报告表明环境不可用，则改为 `credproof/environment_unavailable`，`level: error`，消息写明原因代码。
  - `message.text` 用中文写具体事实，例如“禁止的服务收到 1 次请求，其中 1 次携带了认证凭据”。**任何情况下都不输出凭据值**，即使它是随机合成的。
  - `locations`：`physicalLocation.artifactLocation.uri` 为配置中 `source_scope` 的入口文件，相对仓库根，`uriBaseId: "%SRCROOT%"`；`region.startLine: 1`。运行时事实没有具体行号，因此定位到文件级。
  - `partialFingerprints.credproofCondition/v1`：用 `sha256(配置相对路径 + "\n" + 规则 id)`，保证同一问题跨提交去重，修复后告警自动关闭。
  - `properties`：`verdict`、`report_sha256`、`project_tree_sha256`、`duration_ms`。
- `runs[0].automationDetails.id`：`credproof/<配置相对路径>/`。同一仓库检查多个项目时，各自独立成类。
- `runs[0].invocations[0].executionSuccessful`：仅当检查完整执行（PASS 或 FAIL）时为 true。
- 测试：用 SARIF 2.1.0 官方 JSON Schema 校验 PASS、FAIL、UNKNOWN 三种输出。Schema 以文件形式放进测试数据，不在测试时联网下载。另外断言输出中不含凭据、绝对路径和用户名。

### 3.3 JUnit 与摘要

- **JUnit**（GitLab、Jenkins、Azure DevOps 通用）：一个 `testsuite name="credproof"`。
  - PASS / FAIL：14 个 `testcase`，每项条件一个，未满足的带 `<failure message="事实">`。
  - UNKNOWN：一个 `testcase name="evidence_complete"`，带 `<error>`。
- **摘要 Markdown**：结论、未满足的条件和事实、报告摘要、本地复现命令（`credproof-safety check --config …`）。GitHub 上把它写入 `$GITHUB_STEP_SUMMARY`。

### 3.4 GitHub Actions

新增可复用示例 `.github/workflows/credproof.yml`：

- 触发：`pull_request`，以及手动触发 `workflow_dispatch`。
- 权限：`contents: read`、`security-events: write`。
- 所有第三方 action **固定到提交 SHA**（`actions/checkout`、`github/codeql-action/upload-sarif`）。
- 步骤：
  1. checkout；
  2. 从同一提交构建镜像，不拉公开镜像；
  3. 运行 `doctor`，失败即停并写摘要；
  4. 对清单 `.credproof/targets.txt` 中的每个配置运行 `check`，带 2.3 节的参数；
  5. 写入摘要；
  6. 上传 SARIF（每个配置一个 category）；
  7. 上传 JUnit 和报告作为构件；
  8. 任一配置退出码非 0，作业即失败。
- 来自 fork 的 PR 没有 `security-events: write`：上传步骤 `continue-on-error: true`，**闸门仍以检查器的退出码为准**，不受上传失败影响。
- 私有仓库没有 GitHub Advanced Security 时，SARIF 上传不可用；摘要和 JUnit 构件仍然有效，文档中写明。
- AppArmor：按 2.3 节的实测结论在工作流中处理，并说明原因。

另提供 `docs/integration/ci.md`，给出 GitLab CI 和 Jenkins 的通用 `docker run` 片段（产出 JUnit），标注“未实测”。

### 3.5 演示 PR（商业价值证据）

在仓库中用 `examples/bench/b07-webhook-relay` 做两条演示 PR，目标分支为演示分支，不合并：

1. **漏洞版补丁**：入口文件换成 b07 漏洞原版，与 Qwen3-Coder 交回的补丁逐字节相同。预期：业务测试全绿，CredProof 作业变红，代码扫描出现 3 条告警：入口场景、禁止服务收到请求、未授权连接。
2. **参考修复**：预期作业变绿，上一条 PR 的告警在合并基线上不出现。

截图保存到 `docs/integration/evidence/`，**截图中的账号、仓库名先打码**。这是报告和答辩中“接进现有研发流程”的直接证据。

## 4. 分工与 PR 拆分（按顺序，后一个基于前一个合并后的主线）

| PR | 负责 | 内容 | 预计 |
| --- | --- | --- | --- |
| A | 5060 | `credproof_safety/report_formats.py`（SARIF、JUnit、摘要）；`cli.py` 新增 `--sarif/--junit/--summary`；argparse 退出码修正为 4；SARIF Schema 校验测试和隐私断言。属于受保护目录，由 5090 评审 | 半天 |
| B | 5090 | `scripts/runtime/setup-linux.py`；锁文件补哈希；`doctor.py` 及子命令；`deploy/docker/`（Dockerfile、seccomp profile、AppArmor profile 或结论）；`docs/integration/linux.md`；镜像扫描；Linux 与 Docker 的实测收据 | 1 天 |
| C | 5090 | `.github/workflows/credproof.yml`、`.credproof/targets.txt`、两条演示 PR 及截图；`docs/integration/ci.md`。5060 评审文档和截图 | 半天 |

A 与 B 可以并行；B 修改 `cli.py` 时只新增 `doctor` 子命令，与 A 的冲突仅限少量行，后合并的一方负责解决。

## 5. 兼容性要求

- Windows + WSL 现有入口（view、recheck、live、交付包）行为不变；交付包的 `check-console.mjs` 和现有测试继续通过。
- `setup-linux.py` 生成的运行时在 WSL 内也能被现有 recheck 使用。若 rootfs 摘要变化，按现有规则要求重新探测，不复用旧的就绪状态。
- 报告 JSON 结构不变。三种新格式都由它派生，不反向影响判定。

## 6. 验收清单（全部满足才算第三、四步完成）

1. **Docker**：按 2.3 节参数（自定义 seccomp，不用 unconfined），镜像内对 8 个 bench 目标的漏洞原版和参考修复各检查一次，16 个结论与 `docs/bench/bench-results.json` 中的锚点结论**逐一一致**。
2. **安全失败**：用 Docker 默认参数运行时，`doctor` 退出 4 并给出对应提示，`check` 返回 UNKNOWN、退出 3。任何情况下都不得出现 PASS。
3. **原生 Linux**：在一台不是 WSL 的 Ubuntu 24.04（或 22.04）上，`setup-linux.py` → `doctor` → `check`，同样得到 16 个一致的结论。
4. **SARIF**：PASS、FAIL、UNKNOWN 三种样例通过官方 Schema 校验；不含凭据、绝对路径、用户名。
5. **GitHub Actions**：在 GitHub 托管的 ubuntu-24.04 runner 上实际运行；两条演示 PR 结果符合 3.5 节，告警截图已打码。
6. **镜像扫描**：敏感命中为 0；构建收据记录基础镜像摘要、apt 版本、wheel 摘要和源码提交。
7. **回归**：Windows 维护测试和交付包浏览器检查仍然通过。

## 7. 隐私扫描

复用 `scripts/delivery/scan.py`，扫描对象扩展到：
- 导出的镜像文件系统（`docker export` 的 tar）；
- SARIF、JUnit、摘要样例；
- 演示截图对应的文字材料。

规则与交付包相同。

## 8. 匿名与发布

- 不推送镜像到 Docker Hub 或 GHCR，镜像只在本地或 CI 中从源码构建。
- 工作流、SARIF 和文档中不出现账号名和仓库地址；截图打码。
- 演示 PR 和 Actions 运行需要仓库处于公开状态，或开启 GitHub Advanced Security。完成取证后，按交付安排把仓库改回私有。
