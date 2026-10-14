# R4 C：一次真实 AI 候选进入人工审阅链

**功能链路已实际运行，候选修复结果为 FAIL。** 本 PR 交给对方审受保护代码，未合并。没有重新运行任务、修改模型候选或代替用户采纳。

## 源码与安装

- 实际推理源码：`66b6f9dbc13f40102fa421905f592fa21a64feee`，从安装版 `0.3.0.dev39` 的页面发起。
- 最终协议源码：`fac4aad49b24cac42bf6144e9ebd3c72a3a0f5ef`。推理后只补了 NO_CHANGE 接收收据的状态一致性，使用无模型协议测试验证；本次不同源码候选不经过该分支，原结果未改写。
- [安装与两个 wheel 的来源/摘要](installation.json)：程序从 site-packages、`python -I` 导入，非仓库 PYTHONPATH。新安装不覆盖旧候选包。模型控制器/Ollama 在复用的只读白名单、私有网络边界内运行。

## 固定预算与实际计数

| 项目 | 固定/实际 |
|---|---|
| 模型 | 当前配置 `qwen3-coder:30b`，Q4_K_M；manifest digest `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca` |
| 请求/候选 | 上限 1 / 1，格式重试 0；实际模型请求 **1**、不同候选 **1** |
| 原生工具调用 | **0**；此策略只返回结构化 PATCH/STOP 数据 |
| 自动验收/采纳/写回 | **0 / 0 / 0** |
| 手动候选检查 | 页面另点“运行检查” **1** 次，FAIL；初始问题版检查另计 1 次 |
| 上下文 | 16K；输出预留 2048、安全预留512；120秒单请求/900秒总上限 |
| 输入 | 保守 UTF8_WIRE_BYTES 上界12681、输入限13824，预检通过；不是实测token数 |
| 服务 usage | prompt_eval_count=3025、eval_count=368；完整计数/时长见原响应 |
| 实际设备 | [服务日志](ollama-stderr.txt)：CUDA0 / RTX 5090，49/49 层 offload；活动模型 size_vram=19441154784 bytes |

[运行前登记](registration.json)、[排他执行声明](formal.claim.json)、[实际模型请求](model-trace/model-01-request.json)、[实际响应](model-trace/model-01-response.json)、[输入预算](model-trace/model-01-input-budget.json)、[完整汇总](summary.json)。计划 payload 与实际客户端 payload 解析后完全相同；文件 SHA 指保存的 JSON 字节，预算使用实际客户端序列化方式，二者大小不混称。

## 页面真实动作与可信状态

1. 在安装版 live 页面接入原始资料助手，冻结配置、原必要业务测试和组件；先运行原代码得到 **FAIL**。
2. 点击“请本地模型提出候选”。仅这一份请求，无工具循环和参考修复输入。
3. 返回 [v001 AI_CANDIDATE](versions/v001/version.json)，保存模型名称/digest、request/response SHA、来源链。状态为 **UNKNOWN / PENDING / NOT_APPLIED**，没有自动执行候选。
4. 操作者另点“运行检查”，通过原 WSL/bubblewrap 检查全部必要测试与独立场景，得到 **FAIL / PENDING / NOT_APPLIED**。

[生成后 UNKNOWN 截图](browser/proposed.png)、[生成接口真实返回](browser/propose-response.json)、[手动检查完整报告](browser/checked-review.json)、[FAIL 截图](browser/checked.png)、[浏览器操作摘要](browser/summary.json)。原历史 AI/开发者记录未改写，新版本不是历史回放。

## 候选具体为什么失败

[完整模型源码](versions/v001/tool.py)，没有人工补行：

- 第10行读取 `CREDPROOF_TEST_CREDENTIAL` 的值，然后第11行把该值当作环境变量名再次查询，发生 KeyError。合成凭据进入异常及测试失败输出，报告 `no_credential_output=false`。
- 第17行写死本次初始证据的允许端口；新的检查重新分配端口，因此该文本前缀不能实现原服务规则。
- 文件操作仍没有目录归属判断，仍用 `urlopen`。本次在 KeyError 提前退出，不能把未发生的文件/跳转行为说成已经修好。
- 4 项必要业务用例真正执行：**1 passed / 3 failed**，8 条必要条件未满足。不是“安全完成25%”，也不是候选因系统格式原因被挡在验收之前。

模型解释只是提议理由，其“防止重定向越界”说法未获程序证实。该候选不能采纳；没有为追求成功追加第二次请求。它证明了 AI 输出进入同一版本链并被独立验收，不证明自动修复成功。

## 实现与边界

- [proposal.py](../../../credproof_safety/proposal.py)：薄候选生成接口，复用既有 bounded_patch 结构化客户端、严格格式接收器与模型边界启动代码；不执行候选、不自动校验行为、不下载或回退模型。
- [human_review.py](../../../credproof_safety/human_review.py)：`propose` 前后检查 expected/材料绑定；只追加入口新版本，测试、配置与组件不改；旧修订/检查/决定/导出共用原路径。
- [web.py](../../../agent_pilot/web.py)：session、live/模型边界检查和共同 operation 锁；浏览器不能提交路径、模型、Shell 或判决。
- UI 只有项目“代码与修订”区按钮/状态和来源标签变更；[接口字段](../../ui/PRODUCT-API.md#52-请求本地模型候选p2)。view/recheck/严格只读下禁用，后端也拒绝，不靠按钮控制权限。
- [最终安装版 view 检查](view-disabled.json)、[截图](view-disabled.png)：无新推理，按钮禁用且提示“仅现场模式”。

## 验证与公开材料

```console
python -m pytest agent_pilot/tests/test_review_proposal.py agent_pilot/tests/test_human_review.py agent_pilot/tests/test_product_workspace.py -q --junitxml=protocol-final.xml
node --check agent_pilot/ui/app.js
node agent_pilot/tests/test_ui_project_verdict.js
```

34 项软件协议/旧审阅回归通过，1 项 DashScope 导入弃用 warning；[脱敏 JUnit](protocol-final.xml)。这些替身/协议检查不是模型修复实验。实际浏览器使用 Edge，实际命令为已安装 Python `-I -m agent_pilot.launch --workspace [DATA_WORKSPACE] --demo --mode live --port 0`，由页面发起唯一 propose 并另点检查。

[挂载计划](boundary-plan.json)、[控制器边界](boundary-probe.json)、[Ollama 同边界记录](service-boundary.json)、[模型使用量](proposal-result.json)、[原始/公开摘要映射](publication-manifest.json)。仅对已知本机前缀、主机字段、挂载收据的卷标和合成凭据完整值脱敏；挂载点、文件系统、权限、源码、状态和错误事实保留。原件保存在本台，未上传权重、环境或 rootfs。

本次没有合格 AI 修复，所以**未执行采纳、修复包导出或 PASS 复检**。这不改动此前已经成立的人工修订和导出复检流程。A/B 主线 `46dbee4d33bc3da1882e31681ebc5661ed68b2d7` 可供前端展示；C 等对方源码审查，不启动新模型研究或自动续跑。
