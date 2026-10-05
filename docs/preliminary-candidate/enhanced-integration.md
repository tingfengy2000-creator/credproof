# 增强候选版：从体验示例到项目复检

这页是给评委和第一次使用者的最短操作说明。它描述的是当前候选版已经接上的流程，不把历史回放写成新的模型推理。

## 1. 先看懂它检查什么

CredProof 面向维护自有或获授权 Python 工具的开发者。使用者在启动时登记一个项目配置，写清入口、允许读取的目录、允许访问的本地服务、凭据环境变量和必要业务测试。页面不接收任意路径、命令或网络目标。

一次检查同时回答四个问题：

| 问题 | 实际依据 |
| --- | --- |
| 工具有没有把合成凭据写入禁止输出？ | stdout、stderr、logging、返回/异常材料中的受控值匹配 |
| 有没有读规定目录之外的文件？ | 隔离执行器记录访问尝试，并区分被拦截和确认读出 |
| 有没有请求未授权服务？ | 本地模拟服务收到的请求与允许服务范围 |
| 原本的任务是否仍然完成？ | 可信 pytest 观察、入口结果、允许认证调用和异常行为 |

缺少必要测试、隔离阻断或材料不适用时，页面显示 `UNKNOWN`；模型文字不能把它变成通过。

## 2. 三步操作

```text
启动时登记项目
    ↓
查看范围 → 现场检查（无模型） → 查看四组结果和代码摘要
    ↓
导出安全测试 → 在项目的新版本目录中重新运行 pytest → 读取新报告
```

Windows 端先在候选包根目录运行：

```powershell
python -m agent_pilot.launch --demo --mode recheck --port 8765
```

页面“体验示例 / 启动时授权项目”只列出启动时登记的项目。选择后：

1. **查看范围**只读取配置和当前对象摘要，不执行项目代码；
2. **现场检查 · 无模型**复制到专用目录，调用同一 `check_project()`，生成新的安全与业务报告；
3. **导出安全测试**生成 `tests/credproof-regression`、范围说明和复检说明。导出的测试每次重新读取当前副本，不能只相信旧 PASS。

现场候选修复仍需 `--mode live`、已经通过门禁的隔离设施、本地 Ollama 和固定模型。它是单独入口；现场失败不会切换为历史成功回放。

## 3. 三个可讲清的案例

* **资料助手问题版本**：同一后端分别运行凭据输出、越界读取、未授权服务和业务检查。预置修复示例只是人工准备的对照，不称为现场模型刚刚生成。
* **python-dotenv 外部组件**：保留上游 114 项测试，另有 3 项本项目适配测试；人工注入的越界版本为 116 passed、1 failed。它说明业务测试通过并不替代安全检查，不是新漏洞发现，也不是 Agent 自动修复成绩。
* **h03 历史回放**：第一份候选仍泄露，程序返回真实失败依据，第二份候选改为固定安全错误信息后通过。页面标为 `REPLAY`，不能冒充本轮新推理。

## 4. 证据对应

| 结论 | 代码 | 记录 |
| --- | --- | --- |
| 三类安全检查接入同一项目流程 | `credproof_safety/project.py`、`agent_pilot/project_workspace.py` | `experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/project-entry-check.json` |
| 导出测试必须实际通过/实际失败 | `scripts/run-exported-regression-check.py` | `experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/exported-regression-v4/` |
| 页面不接受任意路径或命令 | `agent_pilot/web.py`、`agent_pilot/ui/app.js` | `agent_pilot/tests/test_project_workspace.py`、定向回归日志 |
| 外部组件与历史结果分开 | `agent_pilot/external_twine.py`、`docs/external-scenario/twine/` | `docs/preliminary-candidate/evidence-index.md` |

## 5. 运行边界

历史查看不需要 GPU 或模型；重新验收需要已有隔离设施但不调用模型；现场新推理才需要本地模型。当前验证范围是同一台 Windows + WSL Ubuntu 24.04 机器上的受控 Python 样例和一个窄外部组件，模型权重、虚拟环境和真实凭据不在候选包中。普通哈希只能发现相对清单变化，不是第三方认证或不可伪造证明。

