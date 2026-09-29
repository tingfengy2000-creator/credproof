# 本地 Agent 试验的候选执行隔离

本文件记录已实现的 Linux 候选执行边界。它保护宿主文件、网络和计算资源；它不等于虚拟机隔离，也不是候选功能正确、凭据零泄露或判定器不可欺骗的证明。本阶段只执行了固定、自编写的隔离探针，案例和模型补丁由总试验入口另行运行和保存结果。

## 实际环境与依赖来源

当前配置固定为 Windows → WSL `Ubuntu-24.04`、用户 `tingfeng`（准备阶段实际 UID 1000）、x86_64、系统 Python 3.12.3、内核 `6.18.33.2-microsoft-standard-WSL2`。可信运行设施固定在 `/home/tingfeng/credproof-agent-runtime/isolation`，不会跟随服务进程的 HOME，也不接受 API 传入任意设施路径。

`bubblewrap 0.9.0-1ubuntu0.3` 来自 Ubuntu 官方 `noble-security` 索引。准备过程先使用系统 Ubuntu archive keyring 验证 InRelease 签名，再校验 Packages.xz 的 SHA256，并取得包条目；程序按冻结的包摘要下载，仅用 `dpkg-deb -x` 解包到专用目录，没有全局安装软件包。旧本地 apt 缓存列出的版本下载返回 404，未继续使用该旧缓存。

| 对象 | SHA256 |
| --- | --- |
| 官方 `.deb` | `2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094` |
| 解包的 `bwrap` | `e318903862396f96de3df57264e0158682b952fd3fb53ac23d876413e7b30f71` |
| 当前 `sandbox_runner.py` | `06fa4f031fa10a5669921ed18d88dab55ceb6e057a2ef0dddc00f55c24887947` |
| 复制的 Python rootfs | `bb05d259a490032bd749a7c26fe58f3f9a37d4a22e7939784f4a2c62afead52c` |
| seccomp BPF | `9b004542224d5348953d41f468ec8b45c14508329fc42cd2cd96d03ed44113da` |

官方签名、索引和取得过程的记录保留在 Linux 专用运行目录的 `bootstrap-metadata`。这些摘要用于匹配本机已审查设施，没有远程认证或第三方认证含义。

## 两层边界

外层由总试验启动器负责：可信 Ollama 服务和可信 Agent 进入同一个新 user/network namespace，只开启 loopback，不创建 veth 或外部路由；模型下载准备与正式运行分离。服务专用 HOME 可以设为 `/home/tingfeng/credproof-agent-runtime/service-home`。外层不是候选代码的执行边界。

内层由 `sandbox_runner.py` 负责，每次调用创建独立 bubblewrap 子进程：

1. 创建新的 user、mount、PID、network、IPC、UTS namespace；丢弃所有 capabilities，启用 no-new-privileges、独立 session 和 die-with-parent。
2. 根目录来自预先复制的 Python 可执行文件、标准库和其动态库，整体只读。没有绑定宿主 `/`、`/home`、E 盘、项目仓库、模型目录、账户配置或 GPU 设备。
3. 本次代码文本仅形成 `/work/tool.py` 和 `/work/runner.py`，该目录只读。候选看不到用例标签、隐藏矩阵、总判定器或原始会话。
4. `/proc` 来自内层 PID namespace；`/dev` 只含 bubblewrap 构造的基础设备并重挂只读，不能向设备目录写普通文件。唯一文件暂存区 `/tmp` 是独立、16 MiB 的 tmpfs。
5. 环境清空后只设置 PATH、HOME、LANG、TMPDIR；关闭继承文件描述符，仅保留 stdin/stdout/stderr 及启动时交付 seccomp 所需的 FD，最终候选中检查描述符范围。候选使用 `python3 -I -B`，工作目录为 `/work`。

seccomp 使用本机架构过滤器：拒绝 socket/connect 等网络系统调用、fork/clone 等创建进程与线程的调用、unshare/setns、mount/chroot、ptrace、跨进程内存访问、BPF、keyring、io_uring 等。它采用明确拒绝列表，不冒充经过形式验证的系统调用白名单。`execve` 保留给 Python 启动使用，但可访问的执行环境只含准备的 Python rootfs，资源限制在 exec 后仍继承。候选无权重新建立 namespace 或获得 capabilities。

## 限额、停止和门禁

| 项目 | 当前固定限额 |
| --- | --- |
| 地址空间 | 256 MiB，RLIMIT_AS |
| CPU 时间 | 3 秒，软硬上限相同 |
| wall time | 默认 10 秒，可选 0.2–15 秒 |
| stdout + stderr | 合计 256 KiB，达到限制后终止 |
| 单文件大小 | 4 MiB |
| 打开 FD | 32 |
| core dump / 锁定内存 | 0 |
| `/tmp` 文件系统容量 | 16 MiB |
| 候选 / harness / JSON 输入 | 64 KiB / 128 KiB / 32 KiB |

目前没有 cgroup 配额；该限定任务使用一个候选解释器且禁止 fork/clone。RLIMIT_AS 不是总系统 RSS 承诺，系统共享内核、受信任 bwrap 管理进程和父监督进程不属于候选地址空间。限额之外，父进程以非阻塞管道采集输出并执行 wall-time、输出量终止；没有失败后在宿主直接执行的回退路径。

`prepare_isolation()` 仅允许非 root Linux 准备操作，并将准备结果置为未就绪。`probe_isolation()` 只运行仓库内固定探针。`run_isolated()` 每次重新计算 supervisor、rootfs、bwrap、seccomp 和内核身份，与通过探针的收据核对；缺失、未通过或身份漂移均返回 `ISOLATION_ERROR`，不启动候选。外层映射 root 的 run/probe 已实际测试可用；真实宿主 root 不用于准备阶段。

设施目录仅受可信本地操作者管理。本机制不对具有同等宿主写权限的恶意进程提供防篡改证明，也没有解决“身份检查后另一宿主进程同时换文件”的对抗性竞态。正式运行期间应保持设施不变；修改 supervisor 后必须重新准备、探测并保留新观察目录。

## 调用契约与结果使用

```python
from agent_pilot.isolation import run_isolated
from agent_pilot.judge import trusted_harness_source

result = run_isolated(
    candidate_code=source_text,
    harness_code=trusted_harness_source(),
    input_data={
        "request": selected_request,
        "auth_mode": "success",  # 或 denied / provider_error
        # credential 可省略，由隔离侧随机生成，仅供合成试验
    },
    timeout_seconds=10,
)
```

调用者只能传文本和 JSON，不传宿主目录。Windows 入口将可信 supervisor 源码和上述数据通过 WSL stdin 传送；Linux 入口直接调用可信 supervisor。两种入口都不会在可信进程中导入、eval 或 exec 候选文本。

执行结果包含 `status`、`returncode`、`stdout`、`stderr`、`duration_ms`、`isolation_receipt`。`status` 可能为 `OK`、`PROCESS_ERROR`、`TIMEOUT`、`OUTPUT_LIMIT`、`ISOLATION_ERROR`。只有 OK 且 stdout 能完整解析为预期 schema 时，外部 judge 才能读取 trial；执行成功不表示功能通过。截断、异常、设施错误都不能转换为 PASS。

stdout 是**私有原始记录**：其中可含本次随机合成凭据及泄露观测，只交给隔离外的 judge。模型和公开结果必须使用 judge 的脱敏反馈。harness 只获得单个请求和本次 mock 模式，不获得隐藏矩阵或期望值。

harness 与候选共享一个 Python 进程，所以不能将其采集结果称为对任意对抗性 Python 代码不可伪造的独立传感器。当前可信代码轮廓检查、语法限制、源文件允许修改约束和外部功能对照属于另一层试验协议；namespace 保护宿主，不自动证明该层 oracle 的抗欺骗能力。没有实际外部凭据验证、真实认证服务或任意仓库脚本运行。

## 已保留的真实检查

最终观察目录为 `agent_pilot/isolation-tests/observations-20260929T062810Z/`，普通环境和外层 `unshare --user --map-root-user --net --fork`、仅 lo up、专用 service-home 环境各 **25 项通过**。检查覆盖六类 namespace ID 实际分离、宿主 home/E 盘/宿主 PID 根不可见、无 dxg/dri、空路由、socket/fork/unshare 拒绝、capabilities 为零、no-new-privileges、seccomp、root/work/dev 只读、shm 缺失或只读、16 MiB 暂存区、环境及 FD 清理、内存、CPU、输出量及超时终止。

`test_isolation.py` 的 **7 项测试通过**：两类保留探针与当前 supervisor 身份相符；服务 HOME 不改变设施路径；缺失/未通过收据不启动进程；运行时、bwrap、过滤器或 supervisor 漂移关闭门禁；越界输入在创建子进程前拒绝；基础探针失败或缺项不能被后续限额探针“投票通过”；中断重新探测会使旧绿色收据失效。测试只使用临时假设施和固定探针记录，没有执行模型补丁或案例。

最终代码审阅曾发现“基础观察为空，但后续限额检查通过”可能错误聚合为 ready 的失败路径，现已修为必须基本探针成功、必需检查全集存在且全为 True。重新准备和探测开始时均先将就绪门禁关闭；最后一项完整通过后才重新打开。修改前的真实成功探针仍是观察记录，但不可用其 supervisor 身份启动最终试验。

复现命令：

```text
python -m agent_pilot.isolation prepare
python agent_pilot/isolation-tests/record_probes.py
# Linux / WSL 下运行纯门禁回归：
python3 agent_pilot/isolation-tests/test_isolation.py
```

记录器按 UTC 创建新观察目录，不覆盖已有目录。早期调试的 22 项观察仅见工具记录；当时同名 JSON 在收到保留首轮要求前被后续 23 项观察覆盖，因此不将其伪造恢复。顶层两个 `probe-*.json` 是 23 项调试记录，正式引用以上带时间戳的 25 项记录。

本机已经证明这些配置下的具体探针行为；不据此声称能抵御共享 Linux 内核漏洞、未来版本变化或所有恶意程序。升级内核、Python、bubblewrap、过滤器或 supervisor 后应重新审核和执行门禁。

## 技术来源

- [Bubblewrap 官方设计与安全边界](https://github.com/containers/bubblewrap/blob/main/README.md)：空根目录、按需绑定、权限取决于具体调用参数、new-session 等注意事项。
- [Ubuntu 官方 bubblewrap 包](https://archive.ubuntu.com/ubuntu/pool/main/b/bubblewrap/bubblewrap_0.9.0-1ubuntu0.3_amd64.deb)：固定版本与校验来源。
- [unshare(1)](https://man7.org/linux/man-pages/man1/unshare.1.html)、[user_namespaces(7)](https://man7.org/linux/man-pages/man7/user_namespaces.7.html)、[mount_namespaces(7)](https://man7.org/linux/man-pages/man7/mount_namespaces.7.html)：命名空间的实际权限和可见性边界。
- [seccomp(2)](https://man7.org/linux/man-pages/man2/seccomp.2.html)、[getrlimit(2)](https://man7.org/linux/man-pages/man2/getrlimit.2.html)：系统调用过滤与资源限额语义。
