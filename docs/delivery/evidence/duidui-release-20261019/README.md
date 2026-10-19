# DUIDUI Windows 运行包定向验收

本次从 `release/duidui-delivery` 的 `7693dcc6f3f9ff301d46d3f988f61fcc257446a4` 建立独立工作区。程序、界面、测试、规则、模型配置均未修改；仅校准根 README 的环境准备步骤。旧运行包及失败记录保留。新增模型调用 **0**。

## 实际操作与结果

| 操作 | 实际结果 | 依据 |
|---|---|---|
| 使用官方 Python 3.12.10 embed 构建并解压到含中文和空格的路径，资源管理器双击 `start-credproof.cmd` | 打开本地首页；无需仓库 `.venv` | `summary.json`；原包摘要见后续最终构建收据 |
| 查看首页、新建检查、我的项目、对照与接入、流水线闸门 | 均可读，浏览器无 JS 错误 | `view-browser-summary.json`、`view-pipeline-dom.txt`、`view-pipeline.png` |
| 新建纯检查 WSL 运行时 | `setup-linux.py` 退出 0；doctor 就绪；不使用旧模型运行时 | `runtime/` 下的实际准备收据 |
| 启动 `start-recheck.cmd`，从页面接入“资料助手（问题版本）”并检查 | v000 **FAIL**，4 项必要测试均执行，2 通过、2 失败；存在输出泄密、禁止目录访问和禁止服务回执 | `recheck/v000/report.json`、`recheck-original-dom.txt`、`recheck-original.png` |
| 页面提交随包 `examples/material_assistant_fixed/tool.py` 作为开发者修订，再检查 | v001 **PASS**，4/4 必要业务测试通过、14/14 条件满足；独立正常返回和跳转场景已执行 | `recheck/v001/report.json`、`recheck-fixed-dom.txt`、`recheck-pass-overview.png` |
| 人工决定及应用 | **PENDING / NOT_APPLIED**；未替参赛者采纳 | 页面状态及 `summary.json` |
| 核对模型准备说明；在另一新目录执行 `isolation prepare → probe` | 固定边界探针 25/25；不调用模型、不执行业务候选 | `model-boundary-preparation.json` |

这里的修订是明确标识的**随包人工修复控制**，不是本轮 AI 生成结果。报告记录的条件、观察范围和限制保持原样，不把测试数量当作安全覆盖率。没有新增模型下载、模型冷安装或推理验收。

最初原生浏览器识别受阻的检查点留在本地，之后通过已连接的应用内浏览器完成上述操作。已完成的 Edge 自动路由检查另外保存，不改写为新运行。`view-browser-summary.json` 中包含实际时间、字体检测、移动宽度及打印检查结果。

## 命令及环境

构建（外部路径由操作者提供，`forbid.json` 不进入仓库或交付目录）：

```text
python scripts/delivery/build_release.py --output <新目录>/DUIDUI队-密证CredProof --python-zip <官方python-3.12.10-embed-amd64.zip> --forbid-file <外部forbid.json>
```

解压目录的 Windows 命令提示符：

```bat
start-credproof.cmd
rem 关闭查看服务后，以随包 Python 运行原 start-recheck.cmd：
set "PATH=%CD%\runtime\python;%PATH%"
start-recheck.cmd
```

第二条启动方式只调整当前命令进程的 PATH；`start-recheck.cmd` 本身尚不自动选择随包 Python。因此根 README 同时提供显式调用随包解释器、自动换端口的命令。正式 ZIP 不包含本机 `config/local-runtime.json`。

WSL Ubuntu 24.04，普通用户，Python 3.12.3；浏览器检查使用 Windows Edge 155.0.4283.45，实际页面修订也通过已连接的应用内浏览器完成：

```sh
python3 scripts/runtime/setup-linux.py --runtime-root ~/credproof-release-20261019 --package-cache <此前已校验的官方bubblewrap.deb>
CREDPROOF_RUNTIME_ROOT=~/credproof-release-20261019 python3 -m credproof_safety doctor
```

独立模型边界准备验证采用新的 `~/credproof-model-precheck-20261019`，复用经过固定 SHA256 核对的官方 deb 缓存，仅预先解包 bwrap，再执行 README 中的 `agent_pilot.isolation prepare` 和 `probe`，未复制模型权重。缓存 SHA256 为 `2461f1beee9cb04c8942739fe1a2b37e7b7c2a3d518f0779dc75f9245baa3094`。

保留一次准备差异：直接在纯检查运行时执行模型 `isolation probe` 会因 runner 标识不同返回 `ISOLATION_ERROR`。未修改纯检查收据来强行通过；README 因而明确使用另一目录，并要求先 prepare 后 probe。该差异不改写资料助手的实际检查结果。

## 文件来源与脱敏

- `recheck/v000`、`recheck/v001` 是本次页面创建的同一项目两版本；保留完整报告、必要测试、配置及入口源码。
- 原始临时工作区已另存到仓库外，退出服务后不依赖临时目录续存。
- `public-mapping.json` 逐文件记录原始与公开字节摘要、长度、精确前缀映射。仅替换已知操作者根路径；容器内 `/tmp/project`、`/tmp/lab` 和必要源码语义不改。报告内合成凭据沿用检查器原本的脱敏结果。
- 证据目录不在运行包白名单中。最终 ZIP 从干净提交重新构建，不从运行后含本地配置和临时数据的目录打包。
- 最终 ZIP 的源码提交、大小、SHA256、禁止词扫描及与已测包的字节对照，另记 `final-delivery.json`；后加收据提交与包内源码提交分开。
