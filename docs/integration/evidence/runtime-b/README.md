# R3 B：Linux 运行时与 Docker 候选配置评审

状态：**实现及本机 WSL 验证已交付；Docker / AppArmor 验收待具备环境后完成。**
本目录不宣称第三、四步已全部通过。没有启动 C、模型推理或新的模型实验。

- 契约合并基线：`2a94ef8d6777676aba22e3ed68c23817c5f6aed2`。
- 被测源代码：`1b56c7fdc52042c5e9250c1446f17637805c8683`，分支 `feat/linux-runtime-5090`。
- wheel 构建于 `7261e4c936f8ff15460de022ee7a9ccdd3690cc3`；后续只增加验证脚本、修正软件测试的主机假设。安装后的五个核心模块逐文件与被测源码核对相同，详见 [安装来源](wsl-anchors/installation.json)。
- wheel：`credproof_safety-0.3.0.dev38-py3-none-any.whl`，349,987 bytes，SHA256 `2cdd2a1030853c2d68e54dc7b7cf25a5c4c9543e1981d45ffc516ab421c77486`。wheel 本身不入 Git。
- 后续交付提交增加文档、许可和脱敏证据，不混作另一轮安全实验。

## 实现与对应证据

| 内容 | 代码 | 实际依据 |
| --- | --- | --- |
| 专用有限 rootfs、哈希锁、无损复用与拒绝 | [setup-linux.py](../../../../scripts/runtime/setup-linux.py)、[runtime_setup.py](../../../../credproof_safety/runtime_setup.py) | [完整 rootfs 清单](rootfs-manifest.json)、[复用前后摘要](wsl-anchors/reuse.json)、[缺清单拒绝](wsl-anchors/mismatch.json)、[官方依赖来源](dependency-sources.json) |
| 无害固定探针，不执行项目 | [doctor.py](../../../../credproof_safety/doctor.py) | [实际 doctor](wsl-anchors/doctor.json)、[WSL CLI 输出](preparation/b-doctor-wsl.stdout.txt)：exit 0；Windows 原生 doctor 明确不支持，exit 4 |
| 安装版调用原可信检查器 | [verify-anchors.py](../../../../scripts/runtime/verify-anchors.py) | [16 项汇总及实际命令](wsl-anchors/summary.json)，每项目录含 command.json、report.json、stdout/stderr |
| Windows 桥接未退化 | 原 runner/check_project 未修改 | [Windows wheel 来源/命令](windows-bridge/receipt.json)、[漏洞原件 FAIL](windows-bridge/vulnerable.json)、[人工参考 PASS](windows-bridge/reference.json) |
| 容器候选与隐私工具 | [Dockerfile](../../../../deploy/docker/Dockerfile)、[seccomp 来源/增量](../../../../deploy/docker/seccomp-source.json)、[AppArmor 候选](../../../../deploy/apparmor/credproof-bwrap)、[tar 扫描器](../../../../scripts/runtime/scan-image.py) | 软件回归验证规则来源、clone3 ENOSYS 保留、安全遍历、精确例外、空扫描拒绝；**未构建/执行真实镜像** |

## 实际结果（分开统计）

1. WSL Ubuntu 24.04.4 / Python 3.12.3 / pytest 8.4.2，非 root，新专用运行时：doctor 全部检查 true，rootfs 不含宿主 `/home`、`/workspace`、`/opt/credproof`；复用前后四份准备/清单收据逐字节相同。
2. **现有 16 个锚点**：漏洞原件 8 FAIL（exit 2），人工参考 8 PASS（exit 0），逐项匹配冻结 `docs/bench/bench-results.json`；没有 UNKNOWN 代替 FAIL。每份报告保留必要测试逐 nodeid、入口场景、文件/输出/服务观测。参考修复不是模型生成，本轮模型调用为 0。
3. Windows Python 3.12.14 / pytest 8.4.2：30 passed、2 Linux 专属 skip；WSL：32 passed、无 skip。原失败 JUnit 同时保留，见下方。
4. Windows 干净安装版，`-I`、不使用仓库 PYTHONPATH：b07 原件 FAIL/2、参考修复 PASS/0；WSL 干净安装版 16 锚点均来自 site-packages。
5. `node --check agent_pilot/ui/app.js` exit 0；`node agent_pilot/tests/test_ui_project_verdict.js` exit 0。UI、web、runner、project、credproof_access 的 Git blob 与契约基线逐字节一致；部分 Windows 工作文本仅有 checkout CRLF 差异，[逐文件记录](unchanged-modules.json)分别给出两种摘要。既有页面证据可按该范围沿用，**没有新做浏览器检查或声称本轮页面重新验收通过**。
6. PR #11：固定 `fa2fb83907eda04290e96a1a4a5f53a1f8fd2fa3` 的 Windows 格式测试 **15 passed，0 skipped**；jsonschema 4.26.0 实际执行官方 Schema 校验。[JUnit](software/pr11-windows.xml)。已发布评审（PR #11，评论 6136750594）要求修正访问尝试措辞、可选测试计数、无文件/认证要求的 PASS 摘要；B 不改 A 分支。

## 命令与收据

以下命令的 `<source>` / `<installed>` 是脱敏映射；操作员替换为自己的目录。

```sh
python3 scripts/runtime/setup-linux.py --runtime-root /var/tmp/credproof-runtime-b-r3-20261013-e \
  --package-cache <pinned-official-bubblewrap.deb>
CREDPROOF_CONFIG=/var/tmp/credproof-runtime-b-r3-20261013-e/runtime.json \
  <installed>/bin/python -I -m credproof_safety doctor
<installed>/bin/python -I <source>/scripts/runtime/verify-anchors.py \
  --source <source> --source-commit 1b56c7fdc52042c5e9250c1446f17637805c8683 \
  --runtime /var/tmp/credproof-runtime-b-r3-20261013-e --output <fresh-output>
python -m pytest credproof_safety/tests/test_linux_runtime.py \
  credproof_safety/tests/test_native_runtime.py agent_pilot/tests/test_runtime_config.py \
  -q -ra --junitxml=<evidence.xml>
```

[机器收据](receipt.json)包含原始/派生文件各自大小和 SHA256；[命令与退出码](commands.json)；[最终 Windows JUnit](software/b-windows-final3.xml)；[最终 WSL JUnit](software/b-wsl-final2.xml)。

失败不删除：首次准备缺 system python3.12-venv（exit 4）；`sudo -n` 安装被拒后，操作员通过 WSL root 仅安装官方系统包，准备及检查仍以普通用户运行；旧 `/tmp` 运行时在 WSL 重启后消失；新目录下载出现 TLS EOF（exit 4），未关闭 TLS，改用**已固定摘要的原官方 .deb 缓存**准备另一新目录，未修改旧模型运行时。早期验证脚本从 Linux 读取 Windows worktree 的 `.git` 失败（未执行项目），随后改为由 Windows Git 核实完整 SHA，并实际比较安装模块摘要。

软件测试初次命令用了不存在的测试路径，0 collected / exit 1；新增 Linux 准备测试在 Windows 导入 resource 失败，后来明确按平台跳过；WSL 中两个旧测试硬编码 Windows 路径/全局模拟 nt 导致失败，仅修复测试主机假设。对应 [零收集](software/b-windows.xml)、[Windows 失败](software/b-windows-final.xml)、[WSL 失败](software/b-wsl-final.xml)均保留。最终计数从 JUnit 生成，不将早期失败抹去。

## 尚未验证 / 合并条件

- 本机 Windows 与 WSL 均无 Docker/dockerd，见 [环境记录](environment.json)。因此 Docker 构建、候选 seccomp 实际充分性、默认参数阻断、容器 16 锚点、真实镜像导出/扫描 **未执行**。tar 无害协议样例不是镜像零命中证明。
- AppArmor 配置仅是待宿主加载验证的候选；没有关闭宿主 LSM、没有改全局 sysctl，没有把文件存在当作已启用。
- 非 WSL 的托管 Ubuntu、两个 Actions job、SARIF 实际显示及演示 PR 属于后续 C；A、B 集成前不启动。契约 §6 不标为全部完成。
- A/B 的 CLI 合并冲突及最终合并树的回归仍需集成方执行。本 PR 不合并、不修改 main。

公开材料采用结构化脱敏：只替换实际源目录、安装目录和主机名等已知字段，完整原件保留本地。JSON 仍可解析，失败状态、代码/对象摘要与观察事实不改；派生文本不是原始进程输出字节。`privacy-scan.json` 是**本目录材料扫描**，不是镜像扫描。rootfs 清单公开，rootfs/venv/二进制/权重不上传。
