# 第三、四步契约：Linux / Docker 运行时与 CI 接入

状态：`CONFIRMED_BY_TINGFENG`（R3，5060 起草，按 5090 两轮评审修订；tingfeng 2026-10-13 确认）。已冻结；实现中如需改动，先改本文档、再改代码。
适用主线：`feat/frontend-human-review-5060` @ `37b03f7`。
评审记录：PR #10 评论 6136161052（R1 意见）、6136283652（R2 复核）。

## 0. 目标与非目标

本轮在**已验证的 Ubuntu 24.04（x86_64，Python 3.12）环境**中提供两种用法：

1. **Linux / 容器运行**：不依赖 Windows、WSL、GPU 或模型，执行与 WSL 相同的无模型检查。
2. **CI 闸门**：在拉取请求（PR）上自动检查；结论不是 PASS 时流水线失败，并以 SARIF、JUnit 和流水线摘要给出具体违规事实。

现有证据支持“能接进研发流程”的价值说明。本轮**不是**通用 Linux 生产适配，也不是商业部署认证。

非目标：
- 不改 14 项条件和判定规则，不改 bench-v1 冻结契约；
- 不在 CI 中调用模型；
- 不发布公开镜像；
- 不支持 Windows 原生 CI runner；
- 不承诺 Ubuntu 22.04、Debian 12 等其他发行版（列为待适配，见 2.5）；
- 不改变仓库可见性。仓库是否公开由 tingfeng 另行决定，不属于本契约。

## 1. 5060 预研记录（仅证明可行性，不作为隔离验收）

5060 在 Docker 29.8.2 上用 Ubuntu 24.04（noble）最小系统、`bubblewrap 0.9.0`、`python3 3.12.3` 搭了原型镜像，程序为主线 `37b03f7` 源码，检查器和命令行均未改动。

**注意：原型把 `/` 软链接为 rootfs**，被检查代码因此能只读看到整个容器文件系统。所以下表只说明“容器内可以运行”，**不能作为最终隔离验收**；最终验收必须在专用 rootfs 下重做（第 6 节）。

| 运行参数 | 结果 |
| --- | --- |
| Docker 默认参数 | bwrap 无法创建命名空间；检查器返回 `UNKNOWN / sandbox_execution_incomplete`，没有误报 PASS |
| 只加 `seccomp=unconfined` | 挂载 /proc 失败（Docker 的 /proc 屏蔽路径阻止新 proc 挂载） |
| 只加 `--cap-add SYS_ADMIN` | `pivot_root` 被拒 |
| `seccomp=unconfined` + `systempaths=unconfined`，非 root，不加能力 | 可运行 |
| 上一行再加 `--network none --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges` | 可运行 |
| 上一行环境，b07 漏洞原版 / 参考修复 | FAIL（required_entry_scenarios、no_forbidden_service_receipt、no_unauthorized_connection）/ PASS，与主机一致 |
| `python -m credproof_safety check --config …` | 命令行正常，FAIL 时退出码 2 |

原型宿主没有 AppArmor。自定义 seccomp profile、AppArmor 宿主和 GitHub Actions 均未实测。

## 2. 第四步：统一 Linux 运行时

### 2.1 一个准备脚本，WSL / 原生 Linux / Docker 共用

新增 `scripts/runtime/setup-linux.py`：

- **运行环境**：只在 Linux 内以非 root 用户运行，WSL 也是在 WSL 的 Linux 里运行。Windows 启动入口不直接执行 Linux 准备逻辑。
- **支持范围**：本期只支持 Ubuntu 24.04 / x86_64 / 系统 Python 3.12。其他环境在开始阶段明确拒绝（错误码 4），不尝试兼容。
  - 原因：`runtime_paths()` 固定了 `venv/lib/python3.12/site-packages`，而 `prepare()` 依赖系统 Python 和执行脚本的 Python 是同一版本。
- **运行时目录**：由 `--runtime-root` 指定，布局保持 `agent_pilot.runtime_config.runtime_paths()` 的现有约定。
- **专用 rootfs**：只能是解释器、标准库和必要动态库的有限快照，沿用 `agent_pilot.sandbox_runner.prepare()` 的做法。
  - **禁止**以下替代做法：`/`、任何指向 `/` 的软链接或别名、复制整个容器或宿主根目录。
  - 生成 `rootfs-manifest.json`，内容为：文件清单及摘要、来源（系统包名和版本）、准备脚本版本。
- **bwrap**：使用已固定摘要的 Ubuntu 包，沿用现有 `PACKAGE_URL` 和 `PACKAGE_SHA256`。
- **运行时依赖**：用 `credproof_safety/requirements-lock.txt` 创建 `venv`。锁文件对官方分发文件及**完整传递依赖**补齐哈希，并实际执行 `pip install --require-hashes`。由 5090（B）负责，本契约不视为已完成。
- **配置文件**：写出 `runtime.json`，只含 `runtime_root`。
- **复用规则**：
  - 目标目录已有运行时、且 rootfs 清单、bwrap 摘要、依赖锁摘要全部一致时，校验后无损复用。
  - 任何一项不一致时，**拒绝复用**，要求换用新的、带版本号的 `--runtime-root`。**不自动删除旧目录**，旧目录里可能有模型等保留资产。
  - 脚本不得在重复运行时覆盖已有的准备或探测收据后声称“幂等”。
- **收尾**：最后运行 `doctor`（2.4 节）并打印结果。

### 2.2 Docker 镜像

新增 `deploy/docker/Dockerfile`，采用多阶段构建：

1. `base` 阶段：
   - 基础镜像 `ubuntu:24.04`，**固定镜像摘要**；
   - `apt` 安装 `python3 python3-venv bubblewrap ca-certificates libseccomp2`；
   - 把实际包版本写入构建收据。
2. `runtime` 阶段：以非 root 用户运行 `setup-linux.py --runtime-root /opt/credproof-runtime`。
3. `final` 阶段：
   - 在 `base` 上复制 `/opt/credproof-runtime`；
   - 把**同一提交构建的 wheel** 安装到独立的 `/opt/credproof/venv`；
   - 用户 `checker`（uid 10001）；
   - `ENV CREDPROOF_CONFIG=/opt/credproof-runtime/runtime.json`；
   - `WORKDIR /workspace`；
   - `ENTRYPOINT ["/opt/credproof/venv/bin/credproof-safety"]`。

镜像内不得包含：模型及 Ollama、qwen-agent、`.git`、`docs/handoff/**`、`docs/review/**`、`experiments/**`、真实凭据、作者路径。扫描方法见第 7 节。

- 镜像标签：`credproof:<pyproject 版本>`。
- 构建收据记录：源码提交、wheel 摘要、基础镜像摘要、apt 包版本、rootfs 清单摘要。
- **不推送到任何镜像仓库。**

### 2.3 容器运行参数

```text
docker run --rm \
  --network none --read-only --tmpfs /tmp:exec \
  --cap-drop ALL --security-opt no-new-privileges \
  --security-opt seccomp=deploy/docker/seccomp-credproof.json \
  --security-opt systempaths=unconfined \
  [--security-opt apparmor=<已加载的 profile 名>]  # 仅在需要时，见下
  -v "$PWD:/workspace:ro" -v "$PWD/credproof-out:/out" \
  credproof:<版本> check --config /workspace/<路径>/credproof.toml \
    --source-root /workspace \
    --output /out/report.json --sarif /out/credproof.sarif \
    --junit /out/credproof-junit.xml --summary /out/summary.md
```

**禁止**：`--privileged`、`--cap-add`、以 root 运行、`--network host`。

**seccomp：** `deploy/docker/seccomp-credproof.json`，要求如下。

- **来源**：以 moby/profiles 中**固定提交**的 `default.json` 为基础，文件头部记录来源提交、原文件摘要，以及逐条规则增量。
- **能力前提**：容器使用 `--cap-drop ALL`，因此默认 profile 中只对 `CAP_SYS_ADMIN` 生效的放行规则**不会生效**，不能依赖它们。
- **候选放行清单（必须实测确定，不能预先保证够用）**：`unshare`、`mount`、`umount2`、`pivot_root`、`setns`，以及按参数过滤、只放行必要命名空间标志的 `clone`。
- **`clone3`**：经典 seccomp 无法过滤 `clone3` 的标志，因为标志在指针指向的结构体里。优先保留 Moby 默认对 `clone3` 返回 `ENOSYS` 的处理，让 libc 回退到可过滤的 `clone`。如果实测证明必须整体放行 `clone3`，要单列原因和由此增加的权限，**不得写成已做参数级限制**。
- **最终依据**：清单是否足够，以固定版本的 bwrap、libc、内核，以及 `doctor` 和 16 个锚点的实际执行结果为准。
- **排障选项**：`seccomp=unconfined` 只作为排障手段写进文档，不作为默认值。

**systempaths：**
- 解除 /proc 屏蔽是否必要，以专用 rootfs 下的实测为准。
- 宿主内核、LSM 和 Docker 版本写进收据。

**AppArmor：**
- AppArmor profile **必须由 Docker 宿主加载**。容器内放一个 profile 文件不等于启用。
- 判断依据不能只看 `apparmor_restrict_unprivileged_userns`，还要检查容器实际附着的 profile，以及内核日志中 userns、mount、proc 的拒绝记录。
- **推荐方案**：在宿主显式加载限定 profile（`deploy/apparmor/credproof-bwrap`，附加载命令），用 `apparmor=<该名称>` 启用。
- **另一方案**：如采用 `apparmor=unconfined`，在文档中写明这是“外层 AppArmor 放宽、已实测”的部署选项，由运维显式选择。不自动切换，也不宣称容器仍受 AppArmor 约束。
- **不得修改宿主 sysctl。**

**挂载：** `/workspace` 只读挂载。检查器只在临时目录中复制和运行，输出只写到 `/out`。

### 2.4 `doctor` 自检命令

新增 `credproof-safety doctor`，由 `credproof_safety/doctor.py` 实现，`cli.py` 只负责调用。它不运行任何项目代码，只用固定的自检载荷：

- **配置**：运行时配置可读，版本在支持范围内。
- **rootfs**：存在且不是 `/` 或指向 `/` 的别名；`rootfs-manifest.json` 与实际文件逐一一致。
- **组件**：bwrap 摘要与固定值一致；site-packages 存在，依赖锁摘要一致。
- **隔离能力**：bwrap 能创建 user、net、pid、mount 命名空间并挂载 /proc。
- **沙箱内环境**：`python3 -I` 可以运行，`pytest` 可以导入；沙箱内看不到宿主或容器的 `/home`、`/workspace`、`/opt/credproof`。
- **临时目录**：运行时临时目录可写。

输出 JSON：`{"ready": bool, "checks": {...}, "hints": [...]}`。hints 给出运维下一步操作，例如“容器缺少 systempaths=unconfined”“宿主 AppArmor 拒绝 userns，见 2.3”。

退出码：就绪为 0，未就绪为 4。

### 2.5 原生 Linux（不用 Docker）

文档 `docs/integration/linux.md` 只写已验证的 Ubuntu 24.04 / x86_64 步骤：

1. `apt install python3 python3-venv bubblewrap`
2. `python3 scripts/runtime/setup-linux.py --runtime-root <新目录>`
3. `credproof-safety doctor`
4. `credproof-safety check …`

Ubuntu 22.04（默认 Python 3.10，低于项目最低要求 3.11）和 Debian 12（默认 3.11，与当前固定的 3.12 布局不符）列为“待适配”，不作支持承诺。

## 3. 第三步：CI 接入

### 3.1 命令行输出与退出码

| 命令与结果 | 退出码 |
| --- | --- |
| `check`：PASS | 0 |
| `check`：FAIL | 2 |
| `check`：UNKNOWN（证据不足，包括检查时环境不可用） | 3 |
| 配置错误、参数错误（含子命令参数）、`doctor` 未就绪 | 4 |
| `--help` | 0 |

- 唯一改动：argparse 参数错误（含子命令）当前返回 2，会与 FAIL 混淆，改为 4。
- `doctor` 未就绪返回 4；`check` 因环境不足得出 UNKNOWN 返回 3。两者属于不同命令，互不替代。
- 业务 FAIL 仍为 2。

`check` 新增参数：

- `--source-root <目录>`：仓库根，默认为当前工作目录。CLI 用它和配置文件位置计算相对路径，属于可信上下文。
- `--sarif`、`--junit`、`--summary <文件>`：三者只根据同一份报告字典和 CLI 提供的上下文生成，**不读项目文件、不重新运行**。

路径规则：

- 输出文件中只出现相对于 `--source-root` 的路径，不出现绝对路径、主机名或用户名。
- **入口文件**：由配置中的 `entry.module` 推导为相对于 `[project] root` 的 `<模块路径>.py`（`root` 本身相对于配置文件所在目录），再映射为相对于 `--source-root` 的路径。`source_scope` 是匹配模式，不用于定位。

标准输出仍是原有的报告 JSON，保持兼容。

CI 闸门：`check` 退出码非 0 即失败。UNKNOWN 也失败（安全失败），摘要中写明原因代码，区分“环境不可用”和“证据不完整”。

### 3.2 SARIF 2.1.0 映射

实现位置：`credproof_safety/report_formats.py`。纯函数，输入是报告字典和 CLI 上下文（相对路径、包版本）。

**`runs[0].tool.driver`：**
- `name` 为 `CredProof`，`version` 为包版本；不写 `informationUri`。
- `rules` 固定 16 条：14 项条件各一条，加上 `credproof/evidence_incomplete` 和 `credproof/environment_unavailable`。
- 规则 id 用 `credproof/<条件键>`。`shortDescription` 用中文条件名，`fullDescription` 说明该条件观察的内容。
- `properties.tags` 包含 `security` 和条件所属组（业务保持 / 不泄密 / 不乱读 / 不乱连 / 隔离）。
- `defaultConfiguration.level` 为 `error`。

**`results`：**
- PASS：空数组。
- FAIL：`required_checks` 中每个为 false 的条件生成一条，`level: error`。
- UNKNOWN：生成一条 `credproof/evidence_incomplete`；若报告表明执行环境不可用，则用 `credproof/environment_unavailable`。均为 `level: error`，消息写明原因代码。
- `message.text`：用中文写具体事实，例如“禁止的服务收到 1 次请求，其中 1 次携带了认证凭据”。**任何情况下都不输出凭据值。**
- `locations`：
  - `physicalLocation.artifactLocation.uri` 为 3.1 推导出的入口文件，`uriBaseId: "%SRCROOT%"`。
  - **不写 `region`**：运行时事实没有真实行号，定位只到文件级，不把第 1 行表达成缺陷行。
  - 实现时验证 GitHub 对无 region 结果的显示。若上传被拒，在 PR 中报告并修订本条，不得自行改写成行级定位。
- `partialFingerprints.credproofCondition/v1`：`sha256(配置相对路径 + "\n" + 规则 id)`。它只用于跨提交把同一问题稳定归为一类，**不单独保证告警自动关闭**。
- `properties`：`verdict`、`report_sha256`、`project_tree_sha256`、`duration_ms`。

**其他字段：**
- `runs[0].automationDetails.id`：`credproof/<配置相对路径>/`，同一仓库检查多个项目时各自分类。
- `runs[0].invocations[0].executionSuccessful`：检查完整执行（PASS 或 FAIL）时为 true，UNKNOWN 时为 false。

**测试：**
- 用 SARIF 2.1.0 官方 JSON Schema 校验 PASS、FAIL、UNKNOWN 三种输出。Schema 作为测试数据随仓库保存，不在测试时联网下载。
- 断言输出中不含凭据、绝对路径和用户名。

### 3.3 JUnit 与摘要

- **JUnit**（GitLab、Jenkins、Azure DevOps 通用）：一个 `testsuite name="credproof"`。
  - PASS / FAIL：14 个 `testcase`，每项条件一个；未满足的条件带 `<failure message="事实">`。
  - UNKNOWN：一个 `testcase name="evidence_complete"`，带 `<error>`。
- **摘要 Markdown**：包括结论、未满足的条件及事实、报告摘要，以及本地复现命令（`credproof-safety check --config …`）。在 GitHub 上写入 `$GITHUB_STEP_SUMMARY`。

### 3.4 GitHub Actions

新增 `.github/workflows/credproof.yml`。

- **触发**：只用 `pull_request`。
  - 不用 `workflow_dispatch`：它要求工作流位于默认分支，而默认分支 main 不是项目主线，不为此修改 main。
  - **禁止** `pull_request_target`，也禁止用 PAT 绕过权限，以免以高权限执行不可信代码。
- **权限**：`contents: read`、`security-events: write`。
- 所有第三方 action **固定到提交 SHA**。
- **两个独立 job**，都运行在 GitHub 托管的 `ubuntu-24.04` 虚拟机上：
  1. `native`：不用 Docker，依次运行 `setup-linux.py` → `doctor` → 对清单中每个配置运行 `check`。提供“非 WSL 的原生 Linux”证据。
  2. `container`：从同一提交构建镜像，不拉公开镜像，然后运行 `doctor` → `check`。提供 Docker 证据。
  - AppArmor 按 2.3 的实测结论处理，并在工作流中注释原因。
- **失败后仍保留证据**：
  - 每个 `check` 的退出码先记录下来，后续步骤照常执行：生成并上传已有的报告、JUnit、摘要和 SARIF，最后一步再统一判定 job 失败。
  - `doctor` 失败时同样上传其诊断输出。
  - 不得因 shell 遇到第一个非零退出码就提前结束，导致后续构件丢失。
- **两个 job 各自独立**：各自执行闸门（退出码非 0 即该 job 失败），各自保存完整证据。构件名称带 job 名区分，例如 `credproof-native-<配置>`、`credproof-container-<配置>`，避免互相覆盖。
- **SARIF 上传**：
  - **只由 `container` job 正式上传**到 Code Scanning，每个配置一个 category（即 `automationDetails.id`）。
  - `native` job 生成的 SARIF 只作为构件保存，不上传。原因：同一提交、同一 category 重复上传会互相覆盖或报错。
  - 上传是否可用，取决于事件类型、令牌权限以及仓库的 Code Scanning 是否可用（fork PR、私有仓库是否开启 GitHub Advanced Security 都有影响），按 GitHub 当前规则如实处理，不作统一假设。
  - 上传步骤失败不影响闸门：**闸门只以检查器退出码为准**。JUnit 和摘要构件始终上传。
- **扫描清单**：`.credproof/targets.txt`，每行一个配置路径。

另提供 `docs/integration/ci.md`，给出 GitLab CI 和 Jenkins 的通用 `docker run` 片段（产出 JUnit），标注“未实测”。

### 3.5 演示 PR

用 `examples/bench/b07-webhook-relay` 开两条**互相独立、不合并**的演示 PR：

1. **漏洞版补丁**：入口文件换成 b07 漏洞原版（与 Qwen3-Coder 交回的补丁逐字节相同）。预期：业务测试全绿，CredProof 作业失败，SARIF 和摘要列出 3 项未满足条件（入口场景、禁止服务收到请求、未授权连接）。
2. **参考修复**：预期 CredProof 作业通过。

两条 PR 只证明闸门能分别给出红、绿结论，**不证明告警关闭**，因为没有更新同一分析基线。

截图保存到 `docs/integration/evidence/`，截图中的账号和仓库名先打码。

## 4. 分工与 PR 拆分

A、B 从同一冻结主线（`37b03f7`，或契约合并后的主线）**并行**开分支，分别评审后集成。后合并的一方负责解决 `cli.py` 冲突，并在最终合并树上重跑 A、B 各自的测试。C 基于 A+B 的集成版本开展。A 涉及的受保护文件仍由 5090 评审，所有权边界不变。

| PR | 负责 | 内容 |
| --- | --- | --- |
| A | 5060 | `credproof_safety/report_formats.py`（SARIF、JUnit、摘要）；`cli.py` 新增 `--source-root/--sarif/--junit/--summary`；argparse 参数错误（含子命令）改为 4，`--help` 仍为 0；Schema 校验和隐私断言测试 |
| B | 5090 | `setup-linux.py`（含 rootfs 清单、复用和拒绝规则）；锁文件补全哈希；`doctor.py` 及子命令；`deploy/docker/`（Dockerfile、seccomp profile 及增量说明、AppArmor profile 与加载说明或实测结论）；`docs/integration/linux.md`；镜像扫描（第 7 节） |
| C | 5090 | `.github/workflows/credproof.yml`（native、container 两个 job）；`.credproof/targets.txt`；两条演示 PR 及打码截图；`docs/integration/ci.md`。5060 评审文档和截图 |

## 5. 兼容性要求

- Windows + WSL 现有入口（view、recheck、live、交付包）行为不变；交付包浏览器检查和现有测试继续通过。
- WSL 现有运行时保留，不被删除或覆盖。在 WSL 内用 `setup-linux.py` 新建的版本化运行时，要能被现有 recheck 使用；rootfs 摘要变化时按现有规则重新探测，不复用旧的就绪状态。
- 报告 JSON 结构不变，三种新格式都由它派生，不反向影响判定。

## 6. 验收清单（全部满足才算第三、四步完成）

验收环境：GitHub 托管的 `ubuntu-24.04` 虚拟机（native、container 两个 job），以及 5090 本机的 WSL Ubuntu-24.04。以上**不构成物理机验证或全部 Linux 发行版验证**，文档中如实表述。

1. **专用 rootfs 隔离**：`doctor` 在 native 和 container 中均为 ready，并证明沙箱内看不到 `/home`、`/workspace`、`/opt/credproof`。原型中 `/` 作 rootfs 的结果不计入。
2. **16 个锚点**：8 个 bench 目标的漏洞原版和参考修复，在 native 和 container 中各检查一次，结论与 `docs/bench/bench-results.json` 中的锚点**逐一一致**。
   - 逐例保存必要测试与入口场景的实际执行和观察记录。
   - UNKNOWN 或未执行**不能**替代预期的 FAIL。
3. **安全失败**：在已固定、且已证明会阻断命名空间的参数环境下（例如固定 Docker 版本的默认参数），`doctor` 退出 4，`check` 返回 UNKNOWN（3）。在任何隔离边界没有完整建立的情况下，都不得出现 PASS。
4. **seccomp / AppArmor**：最终 profile 的规则增量、来源提交，以及 AppArmor 的加载方式或放宽理由，均写入收据。默认值不使用 `seccomp=unconfined`。
5. **SARIF**：PASS、FAIL、UNKNOWN 三种样例通过官方 Schema 校验；不含凭据、绝对路径、用户名；GitHub 上的实际显示效果有截图。
6. **GitHub Actions**：两条演示 PR 的结果符合 3.5 节；失败的 job 仍上传了全部构件；截图已打码。
7. **镜像扫描**：符合第 7 节，敏感命中为 0，构建收据完整。
8. **回归**：Windows 维护测试和交付包浏览器检查仍然通过。

## 7. 隐私扫描

镜像使用**专用扫描清单**，与交付包清单不同：交付包规则会拒绝 rootfs 和 venv，而这两者是镜像运行时必需的。

- **扫描对象**：`docker export` 得到的 tar，逐成员安全遍历。
  - 不解包到磁盘；跳过设备文件。
  - 遇到链接时，记录链接本身，不跟随。
  - 拒绝绝对路径和 `..` 路径。
- 记录扫描文件数和字节总数，并按目录给出分布。
- **规则**：与 `scripts/delivery/scan.py` 相同的敏感模式（账号、邮箱、本机路径、主机名、真实凭据格式）。
  - **例外**：只允许明确、可复核的条目，例如某个第三方许可证文件中的联系地址。每条例外写明文件和原因，不得用宽泛的排除规则。
  - 扫描文件数为 0 或范围异常时，判为失败，不能算作 0 命中。
- 同一扫描器也用于 SARIF、JUnit、摘要样例和演示截图的文字材料。

## 8. 匿名与发布

- 不推送镜像到 Docker Hub、GHCR 等任何镜像仓库，镜像只在本地或 CI 中从源码构建。
- 工作流、SARIF 和文档中不出现账号名和仓库地址；截图打码。
- 本契约不包含任何改变仓库可见性的操作。
