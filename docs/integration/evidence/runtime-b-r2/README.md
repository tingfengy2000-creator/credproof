# R3 A/B 复审与合并树验证

本轮只修 PR #12 评审指出的问题并复核 PR #11；没有启动 C、模型或新安全案例集。Docker、AppArmor 和实际镜像扫描继续为 **CANDIDATE**，不能用替代基础镜像复现冒充契约 §6 验收。

## 版本

- A 复核：`1b11425fe0414f13a89ef4d47bad95709f9e4e0e`；已合并为 `454f1ef00920a05821c4fac9ab4bdc3614691b44`。
- B 定向修正：`c72b9606ae003937762ad18ca14dcaf8c5351bb2`。
- **实际被测 A+B 合并树**：`4eb8d5e49cfdbe07e2fa6ae49ed29b53f4c92fed`；无合并冲突。之后提交只增加本说明和脱敏收据。
- [安装包与版本/来源收据](receipt.json)：wheel 363,034 bytes，SHA256 `b7b6ae1968d94433083ff370f0f725f60db28807cba6a7d1a1d35bac6e77f670`；未上传 wheel、rootfs 或虚拟环境。

## 五项修正

| 意见 | 实现与验证 |
| --- | --- |
| 混合行尾导致干净检出变脏 | [.gitattributes](../../../../.gitattributes)对原 `build.stdout.txt` 单文件设 `-text`。原 Git blob、历史摘要和混合行尾均保留。独立 Windows worktree 和 Linux depth=1 全新检出都实际得到空 `git status --porcelain`、空 `git diff HEAD --name-only`；见 [Windows](clean-windows.json)、[Linux](software/r3-linux-clean.json)。这关闭构建脚本的脏树前置阻断，不宣称新生成了交付 ZIP。 |
| tar 扫描性能与边界 | [scan-image.py](../../../../scripts/runtime/scan-image.py)分块哈希、二进制提前跳过文本匹配、必要字符预筛、仅命中时建立行号索引、独立进程硬超时。超过文件/文本/总量/时间限额返回 `SCAN_INCOMPLETE`/4。17MiB 无害软件样例、真实子进程超时、大小限制、JSON 列表参数和大小写路径回归已通过；**不是 647MB 实际镜像扫描结果**。 |
| WSL 写死环境 | [verify-anchors.py](../../../../scripts/runtime/verify-anchors.py)支持 `--environment wsl|native|container`；否则按容器标记/WSL 内核探测，summary 单列环境。旧 summary 不改。 |
| AppArmor 全量放行 | [候选 profile](../../../../deploy/apparmor/credproof-bwrap)移除全量 file/capability/mount，保留固定 Docker-default 的 proc/sys/网络拒绝项，仅声明程序/资料/临时目录权限、指定挂载与三项候选命名空间能力。来源/逐条差异见 [source.json](../../../../deploy/apparmor/source.json)。parser 4.0.1 `-Q -K` exit 0，**没有加载内核，不算实际防护验收**。首次因无效 `rec` 拼写 exit 1 的修正已记入收据。 |
| 重复 bubblewrap | [Dockerfile](../../../../deploy/docker/Dockerfile)删除 apt 安装的 bubblewrap；继续仅使用固定官方 .deb 解出的版本，构建收据不再查询不存在的 apt 包。 |

## 真实检查结果

- A 固定头 Windows 格式测试：**18 passed，0 skipped**，`CREDPROOF_REQUIRE_SARIF_SCHEMA=1`，jsonschema 4.26.0，见 [JUnit](software/pr11-r2-windows.xml)。
- A+B 最终源代码软件套件：Windows Python 3.12.14 / pytest 8.4.2，**251 passed、2 Linux 专属 skip、1 个 SDK 导入弃用 warning**，见 [JUnit](software/r3-ab-windows-installed.xml)。包含 qwen_agent 依赖模块，未运行模型。测试使用独立安装 venv，现有依赖目录仅作为只读测试依赖；没有修改原开发环境。初次缺包元数据的 1 项失败另存 [原 JUnit](software/r3-ab-windows.xml)，没有改程序来隐藏失败。
- WSL Ubuntu 24.04 / Python 3.12.3 / pytest 8.4.2 定向套件：**40 passed，0 skipped**，见 [JUnit](software/r3-ab-wsl.xml)。
- 干净 wheel / `-I` / site-packages 的真实无模型 CLI：doctor **0**、`doctor --bogus` **4**；b07 漏洞原版 **FAIL/2**、人工参考修复 **PASS/0**，见 [来源、命令、逐用例状态](installed-cli/receipt.json)。检查始终在原 WSL/bwrap 运行时执行。
- 同一次检查派生的 SARIF/JUnit/摘要实际生成：漏洞 SARIF 3 条、参考修复 0 条；[真实 SARIF 的官方 Schema 校验](software/r3-cli-schema.json)均通过。详细 [漏洞报告](installed-cli/vulnerable-out/report.json)、[参考修复报告](installed-cli/reference-out/report.json)。不把人工参考修复写成 Agent 成功。
- `node --check agent_pilot/ui/app.js` 和 `node agent_pilot/tests/test_ui_project_verdict.js` 均 exit 0。未重做页面或浏览器展示。

## 复验命令

```powershell
$env:CREDPROOF_REQUIRE_SARIF_SCHEMA='1'
python -m pytest agent_pilot/tests credproof_safety/tests -q -ra --junitxml=<evidence.xml>
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
git status --porcelain
git diff HEAD --name-only
```

```sh
python -m pytest credproof_safety/tests/test_linux_runtime.py \
  credproof_safety/tests/test_native_runtime.py agent_pilot/tests/test_runtime_config.py -q -ra
apparmor_parser -Q -K deploy/apparmor/credproof-bwrap
CREDPROOF_CONFIG=<prepared-runtime>/runtime.json <installed>/bin/python -I -m credproof_safety doctor
<installed>/bin/python -I -m credproof_safety check --config <project>/credproof.toml \
  --source-root <workspace> --output <report.json> --sarif <report.sarif> \
  --junit <junit.xml> --summary <summary.md>
```

## 边界与证据处理

评审者在 PR #12 评论 6145012068 报告的替代 noble 镜像 doctor 4/4/0 与 16/16 锚点，归为**外部候选复现报告**；本台没有重复该实验，也不把它冒充固定镜像/托管 runner 验收。正式容器、AppArmor、完整镜像扫描和 Actions 仍由 C 在 A+B 合并后进行，本轮未启动。

公开资料是 UTF-8 LF 结构化脱敏派生件，以 `-text` 保存准确字节；原件保留，原始/公开 SHA256 分列在 [receipt.json](receipt.json)。只映射明确的源目录、安装目录、主机名和用户名路径，不改状态或业务源码。新增模型调用 **0**；不改 main、不创建 Release。
