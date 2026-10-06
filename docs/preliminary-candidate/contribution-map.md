# 贡献与证据映射

本表只写当前可核对的工程增量；模型、Agent 框架、推理服务、pytest、隔离工具和上游组件按来源归属。

| 具体困难 | 本项目实现 | 相比什么多做一步 | 代码与证据 | 边界 |
|---|---|---|---|---|
| 表面脱敏可能留下真实值 | 将受控失败证据反馈给下一候选 | 相比一次性模型修复，允许根据当前反例再调整 | `agent_pilot/reliability.py`；h03 两份候选与两次验证 | 单个反馈实例，不是普遍优势 |
| 业务测试通过不等于没有泄露 | 同时检查输出、文件、网络和必要业务状态 | 相比只看 pytest 或模型文本，程序计算联合判决 | `credproof_safety/project.py`、`agent_pilot/judge.py`；python-dotenv 117/117 业务通过仍 FAIL | 受控 Python 检查矩阵 |
| PASS 可能对应旧副本 | 导出当前对象、规则、报告并重新验收 | 相比保存 PASS 字段，变化后要求重新执行 | `agent_pilot/web.py`、`agent_pilot/bundle.py`；导出消费者三副本记录 | 哈希不是认证；历史缺件仍需人工理解 |

## 角色

人工提供授权范围、必要测试和业务接受条件；固定程序生成证据、执行隔离、检查权限并作 verdict；本地模型提出候选和工具调用，不能改裁判或直接指定 PASS。

## 证据入口

- 当前项目区：`agent_pilot/project_workspace.py`、`agent_pilot/ui/app.js`、`experiments/reusable-tool-safety/20261005-enhanced-candidate-v2/`
- 外部组件：`experiments/reusable-tool-safety/20261004-external-dotenv-observer-v2/summary.json`、`20261005-pytest-case-fix-v1/external-dotenv-summary.json`
- 历史 Agent：`experiments/local-agent-pilot/reliability/20260929t095000z-holdout8/comparison/`
- 正式正文：`manuscript.md`
