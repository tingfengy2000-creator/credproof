# PR #1：项目树摘要的跨宿主排序修复

决定采用修复，不把只读查看笼统限制为 Windows。评审对象是 PR #1 的 `95e2bf0e1c65176f050a55ae3a1064ac807f3d00` 及随后仅改说明的 `84d918acd23c42e730d005f76d29fc1fb78c88d4`。原 PR 的 Linux 失败记录保留在 [接收核对](../../handoff/frontend-5060-intake/README.md)，没有改写成通过。

## 根因与最小修改

`sorted(root.rglob('*'))` 使用宿主 Path 的比较规则。Windows 的路径比较折叠大小写，POSIX 区分大小写；同一批精确字节，`README.md` 与 `credproof.toml` 的先后不同。有序清单再哈希就得到不同摘要。[Python 官方说明](https://docs.python.org/3.12/library/pathlib.html#general-properties)

[检查器 `_digest_tree`](../../../credproof_safety/project.py) 和 [公开材料派生器 `digest_tree`](../../../scripts/derive-project-public-bundle.py) 统一使用显式排序键：`(tuple(part.lower() for part in relative.parts), relative.as_posix())`。第一项保留旧 Windows 排序，第二项区分 POSIX 上仅大小写不同的路径。哈希清单仍记录原始相对路径与精确文件字节；不折叠身份、不转换换行、不取消完整性检查，不接受任意旧摘要作为后备。

正式 v001 项目的旧 Windows 摘要仍为 `d323b459d2b9907555b71cabebd8297c3aef2c4b74919da9266e16dbfed58a3b`；旧 POSIX 原生排序得到 `77b50130df9128c14d1cd3160ba806683e42163d6faffc2fe07b51674fa1a021`。历史报告不修改。如果已有按旧 POSIX 排序创建的报告，应重新检查，不把新摘要补写成旧报告已验证。

## 验证范围与取件

实际结果：Windows Python3.12.14 的26项软件协议测试通过；新 dev36 wheel 在 Windows 和本台 WSL Linux Python3.12.3 各通过5项只读 HTTP 测试，所有执行／审批／导出入口调用为0。安装后的 Linux 直接读取正式快照得到原 `d323b459…` 摘要。5090新目录对同一公开 bundle 重新执行隔离检查得到 `RECHECKED/PASS`：4项必要业务测试实际通过、0skip，14项必要条件全部满足。新增模型调用为0；这一次真实候选复检与上面的只读协议测试分开记录。

[新增定向测试](../../../credproof_safety/tests/test_project_tree_identity.py) 使用真实 PureWindowsPath/PurePosixPath 比较及正式快照，核对旧摘要保持、大小写相邻路径、LF/CRLF 字节差异和既有忽略项。已有项目 bundle、人机审阅、材料绑定测试一起运行；它们是软件协议测试，包含替身报告，不是新的安全案例或模型成功。

- [Windows 协议命令和 JUnit](evidence/trusted-windows/)
- [安装 wheel 与来源收据](evidence/installation/)
- [Windows/Linux 已安装版本只读 HTTP 验证](evidence/readonly/)
- [同一公开 bundle 的5090无模型复检](evidence/recheck/)
- [总收据：源码 SHA、实际结果和文件摘要](evidence/review-receipt.json)

安装与查看命令见 [交接入口](../../handoff/frontend-5060/README.md)。只读查看不需要 GPU、模型、WSL 或候选执行。Linux 验证若通过，只证明本台5090的 WSL Linux 只读链路；不冒称另一台5060已实测、macOS已实测或任意系统均可动态验收。真实动态检查仍使用5090已有 Windows+WSL/bubblewrap 环境。

本修复在独立 `review/pr1-tree-identity` worktree/分支完成；未合并 PR #1、未修改 main、未移动保留基线或旧标签。新增模型调用为0，不替用户采纳任何业务修复。完整结果以总收据为准，不能把源码修复提交当作随后安装测试已发生。

准备阶段原沙箱测试受 `Path.resolve` 文件权限限制；同样测试在可信本机环境通过。Linux 系统 Python 缺 ensurepip，改用新建无pip venv和已有可信pip的 `--python` 离线安装，不修改系统环境。失败位置及后续成功命令分别保留。新 wheel 比旧 wheel 小，是因为干净 worktree 没有旧 wheel 带入的33个未跟踪 `__pycache__/*.pyc`；共同程序文件除本次 `project.py` 外仅有5个LF/CRLF字节差异，详见安装清单和来源说明。没有以新报告覆盖历史失败。
