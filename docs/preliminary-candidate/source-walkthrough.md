# 源码讲解与五个关键追问

推荐按“项目接入 → 固定检查 → 候选/反馈 → 导出复检”讲解。源码重点如下。

1. **项目边界和三类观察：** 打开 `examples/material_assistant/credproof.toml`、`agent_pilot/project_workspace.py` 和 `credproof_safety/project.py`。可以说：“入口、源码范围、允许目录/服务、凭据变量和必要 pytest 由人工固定；程序只在专用副本观察输出、文件和网络。”
2. **程序判决：** 打开 `credproof_safety/project.py` 的 `check_project`/`_verdict`，再看 `agent_pilot/ui/app.js` 的 `renderProjectModes`。可以说：“后台总体 verdict 独立显示。业务、认证和三类安全检查的局部 PASS 不能覆盖总体 FAIL；缺材料或旧对象是 UNKNOWN。”
3. **候选与反馈：** 打开 `agent_pilot/reliability.py` 的 `authority`、`submit`、`run_method`，以及 `model_client.py`。可以说：“模型只读取允许代码和脱敏观察，提交候选；h03 的第一份补丁被真实反例拒绝，失败回执进入下一请求。”
4. **对象复检：** 打开 `agent_pilot/web.py` 的 `_require_current_material` 和 `agent_pilot/bundle.py` 的 `recheck_bundle`。可以说：“导出和复检绑定当前副本与条件，变化后旧报告不能继续显示为当前通过。”
5. **外部证据：** 打开 `experiments/reusable-tool-safety/20261004-external-dotenv-observer-v2/summary.json`。这是 python-dotenv v1.2.2 的人工注入副本，不调用模型；117 项业务通过但重新引入安全缺陷仍 FAIL。

## 1 这与扫描器或 CI 有什么区别

扫描器和规范 CI 仍是基础能力，也可以实现很多固定检查。CredProof 的实际增量是把当前副本的输出/文件/网络证据、候选补丁、必要业务检查和对象复检放到同一条受控流程中；它不声称替代扫描器或 CI。

## 2 模型解释错了或提了危险补丁怎么办

模型不能指定 verdict 或越权写入。程序按路径、工具参数、修改范围、真实凭据输出和业务条件拒绝候选。h03 的模型根因解释曾不准确，但真实日志反例仍把第一份候选判为 FAIL。

## 3 为什么用 Agent 而不是固定脚本

固定脚本适合已知模式，应继续保留。Agent 的有限作用是阅读受限代码、选择结构化工具并根据执行反馈改变候选；h01 和 h03 各自给出一个受控实例。没有证明它在所有任务更好，也没有测量人工时间收益；查看和重新验收无需模型。

## 4 为什么外部 python-dotenv 不是上游漏洞

接入固定 v1.2.2 和 BSD-3-Clause 许可，缺陷是本项目在一次性副本中人工注入的目录越界读与输出问题。它验证适配、验收和复检链路，不代表 CVE、上游采纳或企业部署，也不替代官方升级。

## 5 哪些是自己实现的，复检能证明什么

模型、Agent 框架、推理服务、pytest、隔离基础和上游组件按来源归属；受限工具、观察/判决、项目材料绑定、导出测试和页面判决由本项目实现，Codex/ChatGPT 对开发有实质辅助。复检证明对应副本在已覆盖条件下重新得到的结果；哈希和材料完整性不是第三方认证，不证明所有输入或生产环境安全。AI 辅助参赛规则仍由本人确认。
