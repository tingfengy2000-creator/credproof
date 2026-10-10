# 贡献与证据映射：AI辅助修复与人工采纳

| 实际问题 | 自行实现 | 用户获得什么 | 源码/证据 | 边界 |
|---|---|---|---|---|
| AI建议可能遗漏导入、误转异常或改坏业务 | 版本化开发者修订和差异，原输出不覆盖 | 可在模型失败后继续修订，来源可追溯 | credproof_safety/human_review.py:revise；dev35 v000→v001 | 开发者修订/Codex辅助，不是运行时模型PASS |
| 模型或人说正确不能代替实际行为 | 原check_project联合安全与必要业务判决 | 当前修订真实读文件、认证服务且满足边界 | credproof_safety/project.py；dev35 4项必要测试、独立场景 | 已适配Python场景；人工提供规则和业务测试 |
| 绿色检查不代表本人愿意采纳，旧对象不能续用批准 | 独立技术/人工状态；后端重新绑定对象和报告 | PASS仍PENDING，FAIL/UNKNOWN不能强行采纳；导出后可复检 | human_review.py:decide/export；project_bundle.py；真实HTTP审批测试 | 本机记录，不是强身份签名；不自动应用原仓库 |

人工确认授权、规则、测试和取舍；本地模型提供候选，固定组件提供安全访问能力；开发者可修订；程序安排执行并计算结论。Qwen-Agent、Qwen模型、Ollama、pytest与WSL/bubblewrap按各自来源归属。审批、哈希、pytest本身不是独创算法。

当前证据入口：[dev35](../reusable-tool-safety/acceptance/20261010-human-review/README.md)。h01仅为相对本项目固定启发式的有限增量，h03仅为历史真实反馈实例；历史八例完整统计保留于正式正文，不与dev35人工修订拼接。
