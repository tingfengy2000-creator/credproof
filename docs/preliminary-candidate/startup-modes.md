# 从查看到现场修复的三种入口

先解压候选包，再在其根目录操作。默认端口为 8765，只监听本机。**停止：回到启动命令所在窗口按 Ctrl+C；看到命令提示符返回后关闭窗口。** 不必结束其他 Python、Ollama 或 WSL 任务。

| 我想做什么 | Windows 入口 | 命令行等价入口 | 实际依赖和边界 |
|---|---|---|---|
| 查看作品 | `start-credproof.cmd` | `python -m agent_pilot.launch --demo --mode view` | 普通 Python；不导入 Qwen、不检查 WSL、不调用模型；禁止动态复检和现场修复，可查看/导出真实历史材料 |
| 重新验收 | `start-recheck.cmd` | `python -m agent_pilot.launch --demo --mode recheck` | 普通 Python + 已准备、通过门禁的 WSL/Linux 隔离设施；不启动模型，禁止现场生成补丁 |
| 现场修复 | `start-live.cmd` | `python -m agent_pilot.launch --demo --mode live` | 已准备的隔离设施、本地 Ollama、固定模型及 Qwen-Agent 依赖；点击现场按钮才开始新推理；失败不回退到回放 |
| 只读检查环境 | `check-runtime.cmd` | `python -m agent_pilot.preflight` | 仅读取配置和既有设施身份，分别报告隔离/模型条件，不安装、不下载、不运行候选 |

同时打开两个模式可使用不同端口，例如 `--port 8786`。浏览器打开命令输出的地址。查看作品入口即使无 GPU/模型/WSL 也能启动；复检入口缺少隔离时无法执行候选，不能降级到宿主 Python。

页面中的“接入项目”区域提供四个真实命令：`init` 写配置模板、`check` 做一次受控检查、`repair` 在有模型和证据时提出候选、`export-tests` 把检查放回项目。用 `--demo` 启动时可选择两个仓库内合成项目，页面提供“查看范围”“现场检查 · 无模型”和“导出安全测试”；接入真实项目时，启动命令显式指定已授权配置，例如：

```powershell
python -m agent_pilot.launch --mode recheck --project-config C:\authorized-tool\credproof.toml
```

网页只接受启动时登记的项目编号，不接收任意路径、代码、命令或远程地址。检查结果来自 `check_project()` 的新副本；页面显示上次对象摘要和报告适用性，代码变化后可重新检查，不沿用旧 PASS。现场检查和导出不调用模型，现场候选修复仍需单独启动 live 模式。

本版实际验证为同一台 Windows + WSL Ubuntu 24.04 机器上的新源码目录、新 Windows Python venv（仅 pip，无 Qwen 等第三方包）及既有隔离 runtime。没有另一台电脑的验证结果。现场模型继续使用原 RTX 5090、qwen3-coder:30b Q4_K_M，权重不随包分发；详细版本、准备方法、配置例子见 [候选入口](README.md#4-配置与首次准备)。作品本次运行未调用付费 API，不把硬件或开发订阅称为零成本。

## 独立材料复检

旧三个演示材料：按各自 `docs/preliminary-candidate/materials/h01`、`h03`、`h07` 中的 README 操作，保持该包自带的验证器版本。

本轮 Twine 材料：

```powershell
cd docs/external-scenario/twine-material-20261003
python -B -m agent_pilot.external_twine recheck .
```

应核对三个独立字段：`old_report_applicable`、`historical_material_integrity`、`new_check.verdict`。它们来自当前材料读取与新的实际执行，不是只显示旧 PASS。命令必须在材料根目录执行，或显式传入材料目录；缺少 `material-manifest.json` 是目录错误，不是验收通过。

## 演示选择

首次接触作品先用查看入口看 h01、h03、h07；准备好隔离后换重新验收入口点击一次复检；需要新推理时再启动现场模式。原模型实验、失败和对照完整保存，不因界面筛选典型案例而修改统计。约三分钟与一分钟视频见 [视频说明](video/README.md)。
