# Windows 评委交付契约

状态：`CONFIRMED_BY_TINGFENG`（2026-10-13，按用户补充定稿）。这是交付约定，不是已经完成全部环境验收的声明。实现与实际验收记录见本目录 evidence/dev38。

## 1. 默认交付与启动

采用**源码及已脱敏展示材料目录 + 官方 Windows embeddable Python 3.12（64 位）**，评委不需要预装 Python、仓库 `.venv`、WSL 或模型。Python 从 python.org 官方发布页取得，原 ZIP 摘要与来源登记；解压到 `runtime/python/`，保留官方许可。`python312._pth` 加入 Windows 相对源码根 `..\..`，不依赖 PYTHONPATH，不加载 site-packages。

评委双击根目录 `start-credproof.cmd`，查找顺序为随包 Python → `py -3.12` → 经实际版本检查的 Python ≥3.11。不会执行 Microsoft Store 的 WindowsApps 占位程序。最低 3.11（tomllib），随包版本 3.12.10；开发测试版本 3.12.14，均以实际收据为准。

有随包 Python 时，cmd 直接执行 `runtime\python\python.exe -S -m agent_pilot.launch`，不经过 PowerShell。不含执行策略绕过；只有缺少随包 Python 才调用 `launch.ps1` 查找系统解释器。学校策略禁用 PowerShell 时，恢复完整随包运行时即可使用默认入口，无需改变系统策略。

启动器自动打开浏览器；8765 被占用时绑定系统分配的空闲端口，打印并打开实际地址。失败保留窗口、显示原因及下一步。macOS/Linux 可用 `sh start-credproof.sh`，或 `python3 -S -m agent_pilot.launch --demo --mode view --auto-port --open-browser`（需预装 Python ≥3.11；本轮不宣称已跨系统实测）。

源码和展示数据来自同一固定 Git 提交，另附文件摘要。已安装 wheel 是开发者可选入口：在独立安装环境运行 `python -I -m agent_pilot.launch --workspace <交付目录> --demo --mode view`；wheel 提供程序和 UI，workspace 提供 bench、历史案例和审阅快照，二者版本必须登记。不把只安装 wheel 等同于已经取得历史材料。

## 2. 不装 WSL 的查看体验

`view` 必须提供：概览矩阵（冻结 bench 结果）、补丁记录及验收报告、h01/h03/h07 精选历史回放、dev35 人工审阅故事（AI v000 FAIL → 开发者 v001 PASS → PENDING / NOT_APPLIED，审批功能测试记录另标）。所有既有结果明确为历史记录，打开页面不启动模型、不探测 WSL、不执行候选代码。

历史原件只读；每次启动验证冻结清单，复制到系统临时目录下的随机工作区，正常退出时清理。临时目录不可写则明确报错，不静默忽略或写回原件。查看模式允许的修订、决定及静态导出仅作用于临时副本，并标为演示，不代表参赛者真实采纳。动态重新验收和现场修复在 view 模式由后端拒绝。

临时目录使用 `credproof-demo-review-*` 和本程序的 `owner.json`（PID、启动时间、固定 schema）。启动时仅删除系统临时目录直接子项中标记有效、不是链接且所属进程确认已退出的目录；活跃实例即使超过 12 小时也保留，权限不明、损坏标记和旧无标记目录均不删除。Windows 使用只读进程查询，不杀进程。Ctrl+C 和 Windows Ctrl+Break 走正常清理；强制关闭/断电可能留下标记目录，下次启动再清理，不承诺强制结束时立即清理。

## 3. 重新验收与现场修复

- `start-recheck.cmd`：仅限已准备并预检通过的 Windows + WSL/bubblewrap 受控运行环境，需要对应业务测试依赖，不调用模型。
- `start-live.cmd`：在相同隔离条件上增加已登记的本地 Ollama、固定模型权重和可信安装解释器；不自动回退收费 API、旧解释器或历史回放。
- 缺隔离、模型或配置时，页面显示缺项及该操作被阻断的原因；历史仍可阅读。不能降级到宿主执行项目代码。查看按钮与动态操作须有清楚区别。

这两种动态模式由安全验收工作机完成验证；不要求评委预装它们才能查看作品，不承诺所有机器动态运行。内部机器代称不进入交付界面。

## 4. 交付目录

```text
credproof/
  start-credproof.cmd       # 默认历史查看
  start-recheck.cmd         # 需要已准备的隔离环境
  start-live.cmd            # 另需本地模型与可信安装解释器
  agent_pilot/              # 程序、UI、受控登记样例
  credproof_safety/         # 检查、人工审阅与导出
  credproof_access/         # 安全访问组件
  config/runtime.example.json
  runtime/python/           # 官方 embeddable Python，仅 Windows 查看
  scripts/delivery/         # 启动与脱敏扫描；构建工具保留在源码仓库
  docs/bench/bench-results.json # 内含固定结果与逐补丁报告
  docs/reusable-tool-safety/acceptance/20261010-human-review/public-evidence/workspace/
  experiments/local-agent-pilot/reliability/… # h01/h03/h07 来源
  docs/delivery/VIEWER.md   # 评委使用说明；契约及审查证据仅在仓库
  delivery.json            # 来源版本；文件摘要和扫描收据另附包外
```

白名单以 `scripts/delivery/build.py` 中的明确根目录和文件类型为准：程序包顶层 .py、UI 的 html/js/css、登记样例 manifest/源码/requirements、两个资料助手项目、bench-results.json、dev35 snapshot-manifest 声明的文件、h01/h03/h07 的 C-agent 与 A-fixed 历史、默认配置、启动/扫描脚本、交付使用说明和官方 Python 运行文件。不会遍历复制整个仓库。

不得包含 `.git`、`docs/handoff/**`、`docs/review/**`、其他交接/审查材料、模型权重、rootfs、虚拟环境、真实凭据、机器配置、主机名、用户名及本机绝对路径。公开历史中的本机信息只能形成有说明的脱敏派生件，原始证据本地保留；不能篡改状态或源码语义。`scripts/delivery/scan.py` 扫描整个交付树（含可读 ZIP 内件），敏感命中必须为 0，否则构建失败；报告随交付保存。公开第三方许可联系地址与受控沙箱的虚拟路径不是本机身份，须单列说明，不能通过宽泛忽略跳过任意文件。

## 5. 确认后的验收门槛

在没有本仓库 `.venv`、没有预装 Python 的新 Windows 用户或虚拟机中，将交付包解压到含中文和空格的路径，按默认步骤启动；记录实际 Python/程序来源，运行仓库内 `docs/ui/console-v1/check-console.mjs`（工具及其依赖在交付包外），要求 exit 0，截取人工审阅页 PASS/PENDING/NOT_APPLIED，并保存扫描结果、包大小与摘要。核对冻结文件字节不变。独立目录不能冒称新账户或第二台机器；确实无法建立该环境时如实列为剩余项。

不把合同确认、软件单测、已有历史模型运行或 wheel 安装检查等同于这项交付环境验收完成。
